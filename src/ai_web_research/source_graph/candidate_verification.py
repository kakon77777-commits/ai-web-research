from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, Callable

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.trusted import TrustedExecutionRejected
from ai_web_research.policy.models import PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding

from .fetched_page import FetchedPage, FetchedPageError, fetched_page_from_asset

FETCH_METHOD = VersionRef("method.fetch_document", "1.0.0")
VERIFIER_ID = "reverse_trace.candidate_verifier.v0.1"


class CandidateVerificationError(RuntimeError):
    pass


class CandidateFetchUnavailable(CandidateVerificationError):
    pass


@dataclass(frozen=True)
class TraceCandidateFetchAction:
    source_id: str
    trace_action_id: str
    search_candidate_id: str
    search_provider_id: str
    search_provider_rank: int
    fetch_action: SearchAction


class CandidateFetchStatus(StrEnum):
    FETCHED = "fetched"
    POLICY_REJECTED = "policy_rejected"
    PROVIDER_FAILED = "provider_failed"
    INVALID_DOCUMENT = "invalid_document"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CandidateFetchExecution:
    source_id: str
    trace_action_id: str
    search_candidate_id: str
    fetch_action_id: str
    provider_id: str
    binding_id: str
    status: CandidateFetchStatus
    fetched_page: FetchedPage | None
    observation_id: str | None
    error_code: str | None


def select_fetch_binding(providers: ProviderRegistrySnapshot, provider_preferences: tuple[str, ...] = ()) -> MethodBinding:
    preference_rank={provider_id:index for index,provider_id in enumerate(provider_preferences)}
    compatible=[]
    for binding in providers.bindings:
        if not binding.enabled or binding.method_ref != FETCH_METHOD:
            continue
        try:
            providers.get_provider(binding.provider_ref); providers.surface(binding.provider_ref,binding.surface_id)
        except KeyError:
            continue
        compatible.append(binding)
    if not compatible:
        raise CandidateFetchUnavailable("no enabled fetch-document binding is available")
    compatible.sort(key=lambda b:(preference_rank.get(b.provider_ref.id,len(preference_rank)),b.provider_ref.id,b.binding_id))
    return compatible[0]


def _fetch_action_id(source_id: str, trace_action_id: str, candidate: DiscoveryCandidate, binding: MethodBinding, epoch_id: str) -> str:
    digest=sha256(f"{source_id}|{trace_action_id}|{candidate.candidate_id}|{candidate.url}|{binding.binding_id}|{epoch_id}".encode("utf-8")).hexdigest()[:20]
    return f"reverse-trace-fetch:{digest}"


def compile_candidate_fetch_action(*, source_id: str, trace_action_id: str, candidate: DiscoveryCandidate, binding: MethodBinding, task_id: str, epoch_id: str, created_at: str) -> TraceCandidateFetchAction:
    if binding.method_ref != FETCH_METHOD or not binding.enabled:
        raise CandidateFetchUnavailable("binding is not an enabled fetch-document binding")
    if not isinstance(candidate.url,str) or not candidate.url.strip():
        raise ValueError("candidate URL is required")
    url=candidate.url.strip()
    action_id=_fetch_action_id(source_id,trace_action_id,candidate,binding,epoch_id)
    input_artifact=ArtifactRef(ArtifactKind.CANDIDATE,candidate.candidate_id,metadata={"url":url,"source_id":source_id,"trace_action_id":trace_action_id,"search_provider_id":candidate.provider_id,"search_provider_rank":candidate.provider_rank,"evidence_role":"discovery_only"})
    action=SearchAction(action_id,task_id,epoch_id,FETCH_METHOD,binding.provider_ref,binding.surface_id,binding.binding_id,ActionKind.FETCH,(input_artifact,),{"url":url},(),("document_acquired","candidate_verification_ready"),VERIFIER_ID,created_at)
    return TraceCandidateFetchAction(source_id,trace_action_id,candidate.candidate_id,candidate.provider_id,candidate.provider_rank,action)


async def execute_candidate_fetch_action(compiled: TraceCandidateFetchAction, *, trusted_runtime: Any, execution_context: ExecutionContext, policy_context: PolicyContext, reader: Callable[[str],str], credential_profile_id: str | None = None, fail_fast: bool = True) -> CandidateFetchExecution:
    action=compiled.fetch_action
    try:
        trusted_result=await trusted_runtime.execute(action,execution_context,policy_context,credential_profile_id=credential_profile_id)
    except TrustedExecutionRejected as exc:
        if fail_fast: raise
        return CandidateFetchExecution(compiled.source_id,compiled.trace_action_id,compiled.search_candidate_id,action.action_id,action.provider_ref.id,action.binding_id,CandidateFetchStatus.POLICY_REJECTED,None,None,type(exc).__name__)
    except Exception as exc:
        if fail_fast: raise
        return CandidateFetchExecution(compiled.source_id,compiled.trace_action_id,compiled.search_candidate_id,action.action_id,action.provider_ref.id,action.binding_id,CandidateFetchStatus.PROVIDER_FAILED,None,None,type(exc).__name__)
    observation=getattr(trusted_result,"observation",None); observation_id=getattr(observation,"observation_id",None)
    materialized=tuple(getattr(trusted_result,"materialized_assets",()) or ())
    document_assets=[]
    for item in materialized:
        asset=getattr(item,"asset",None); artifact=getattr(asset,"artifact_ref",None)
        if artifact is not None and artifact.kind is ArtifactKind.DOCUMENT: document_assets.append(asset)
    if not document_assets:
        if fail_fast: raise CandidateVerificationError("candidate fetch produced no materialized DOCUMENT asset")
        return CandidateFetchExecution(compiled.source_id,compiled.trace_action_id,compiled.search_candidate_id,action.action_id,action.provider_ref.id,action.binding_id,CandidateFetchStatus.INVALID_DOCUMENT,None,observation_id,"no_document_asset")
    try:
        page=fetched_page_from_asset(document_assets[0],reader)
    except FetchedPageError as exc:
        if fail_fast: raise CandidateVerificationError(str(exc)) from exc
        return CandidateFetchExecution(compiled.source_id,compiled.trace_action_id,compiled.search_candidate_id,action.action_id,action.provider_ref.id,action.binding_id,CandidateFetchStatus.INVALID_DOCUMENT,None,observation_id,type(exc).__name__)
    return CandidateFetchExecution(compiled.source_id,compiled.trace_action_id,compiled.search_candidate_id,action.action_id,action.provider_ref.id,action.binding_id,CandidateFetchStatus.FETCHED,page,observation_id,None)
