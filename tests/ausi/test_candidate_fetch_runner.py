from types import SimpleNamespace
import pytest
from ai_web_research.core.types import ArtifactKind, ArtifactRef, VersionRef, RiskClass
from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.evidence.models import AcquiredAsset
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.trusted import TrustedExecutionRejected
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.spec import MethodBinding
from ai_web_research.source_graph.candidate_verification import FETCH_METHOD, CandidateFetchStatus, compile_candidate_fetch_action, execute_candidate_fetch_action


def _compiled():
    candidate=DiscoveryCandidate("candidate:1","https://official.example/model-x","Official","snippet","provider.search","surface.search",1,("artifact:1",),{"evidence_role":"discovery_only"})
    binding=MethodBinding("binding.fetch",FETCH_METHOD,VersionRef("provider.fetch","1.0.0"),"surface.fetch","adapter.fetch","1.0.0",True,{}, {})
    return compile_candidate_fetch_action(source_id="source:https://media.example/story",trace_action_id="trace:1",candidate=candidate,binding=binding,task_id="task:1",epoch_id="epoch:1",created_at="2026-09-02T00:00:00Z")


def _contexts():
    return ExecutionContext("task:1","epoch:1","snap",services={}), PolicyContext("task:1","research",None,RiskClass.LOW,(),(AcquisitionAction.FETCH,),"2026-09-02T00:00:00Z")


def _asset(kind=ArtifactKind.DOCUMENT, *, raw_ref="mem://page"):
    artifact=ArtifactRef(kind,"doc:1",metadata={"url":"https://official.example/model-x","fetched_at":"2026-09-02T00:00:01Z","title":"Official page"})
    return AcquiredAsset("asset:1","obs:1","provider.fetch","surface.fetch",artifact,raw_ref,"text/html","2026-09-02T00:00:01Z","hash","usage:1","acq:1")


class Runtime:
    def __init__(self,result=None,exc=None): self.result=result; self.exc=exc
    async def execute(self,*args,**kwargs):
        if self.exc: raise self.exc
        return self.result


@pytest.mark.asyncio
async def test_successful_fetch_requires_document_and_bridges_to_fetched_page():
    execution,policy=_contexts(); result=SimpleNamespace(observation=SimpleNamespace(observation_id="obs:1"),materialized_assets=(SimpleNamespace(asset=_asset()),))
    fetched=await execute_candidate_fetch_action(_compiled(),trusted_runtime=Runtime(result=result),execution_context=execution,policy_context=policy,reader=lambda ref:"<html><body>Official Model X source.</body></html>")
    assert fetched.status is CandidateFetchStatus.FETCHED
    assert fetched.fetched_page is not None
    assert fetched.fetched_page.url=="https://official.example/model-x"
    assert fetched.observation_id=="obs:1"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode",["policy","provider","non_document","missing_content"])
async def test_fetch_failures_are_typed_and_fail_closed(mode):
    execution,policy=_contexts()
    if mode=="policy": runtime=Runtime(exc=TrustedExecutionRejected(SimpleNamespace(authorization=SimpleNamespace(decision="deny")))); expected=CandidateFetchStatus.POLICY_REJECTED
    elif mode=="provider": runtime=Runtime(exc=RuntimeError("network")); expected=CandidateFetchStatus.PROVIDER_FAILED
    elif mode=="non_document": runtime=Runtime(result=SimpleNamespace(observation=SimpleNamespace(observation_id="obs:1"),materialized_assets=(SimpleNamespace(asset=_asset(ArtifactKind.CANDIDATE)),))); expected=CandidateFetchStatus.INVALID_DOCUMENT
    else: runtime=Runtime(result=SimpleNamespace(observation=SimpleNamespace(observation_id="obs:1"),materialized_assets=(SimpleNamespace(asset=_asset(raw_ref=None)),))); expected=CandidateFetchStatus.INVALID_DOCUMENT
    outcome=await execute_candidate_fetch_action(_compiled(),trusted_runtime=runtime,execution_context=execution,policy_context=policy,reader=lambda ref:"<html></html>",fail_fast=False)
    assert outcome.status is expected
    assert outcome.fetched_page is None
    assert outcome.error_code is not None
