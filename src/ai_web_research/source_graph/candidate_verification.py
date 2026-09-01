from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding

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
