from dataclasses import dataclass
from types import SimpleNamespace
import runpy

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, VersionRef
from ai_web_research.evidence.models import AcquiredAsset
from ai_web_research.execution.models import ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.candidate_verification import FETCH_METHOD
from ai_web_research.source_graph.predecessor_verification import PredecessorVerificationStatus
from ai_web_research.source_graph.trace_execution import LEXICAL_METHOD
from ai_web_research.domains.ai_industry.live_discovery import build_ai_daily_from_fetched_pages, expand_ai_daily_reverse_trace, verify_ai_daily_reverse_trace


def _registry(method, provider_id, surface_id, binding_id, capability):
    provider=ProviderSpec(provider_id,"1.0.0",ProviderKind.CRAWLER if method==FETCH_METHOD else ProviderKind.SEARCH_ENGINE,provider_id,(),(),(),(ProviderSurface(surface_id,SurfaceKind.PUBLIC_API,None,frozenset({capability}),None,(),{},{}),),{})
    binding=MethodBinding(binding_id,method,VersionRef(provider_id,"1.0.0"),surface_id,"adapter.fake","1.0.0",True,{}, {})
    return ProviderRegistrySnapshot("snap",(provider,),(binding,))


@dataclass
class TrustedResult:
    observation: ProviderObservation
    materialized_assets: tuple = ()


class SearchRuntime:
    async def execute(self, action, *args, **kwargs):
        q=action.parameters["query"]
        url="https://official.example/model-x" if "available today" in q else "https://repo.example/model-x"
        art=ArtifactRef(ArtifactKind.CANDIDATE,"search:"+url,metadata={"url":url,"provider_rank":1,"evidence_role":"discovery_only"})
        return TrustedResult(ProviderObservation("obs:"+action.action_id,action.action_id,"provider.search","surface.search",ObservationStatus.SUCCEEDED,(art,),None,1,{},None,{},(),"2026-09-02T00:01:00Z",{"query":q,"evidence_role":"discovery_only"}))


class FetchRuntime:
    def __init__(self, html_by_url): self.html_by_url=html_by_url
    async def execute(self, action, *args, **kwargs):
        url=action.parameters["url"]
        if url=="https://official.example/about":
            raise RuntimeError("about page unavailable")
        art=ArtifactRef(ArtifactKind.DOCUMENT,"doc:"+url,metadata={"url":url,"fetched_at":"2026-09-02T00:02:00Z"})
        asset=AcquiredAsset("asset:"+url,"obs:"+url,"provider.fetch","surface.fetch",art,"mem:"+url,"text/html","2026-09-02T00:02:00Z",None,"usage","acq")
        obs=ProviderObservation("obs:"+url,action.action_id,"provider.fetch","surface.fetch",ObservationStatus.SUCCEEDED,(art,),"mem:"+url,1,{},None,{},(),"2026-09-02T00:02:00Z",{})
        return TrustedResult(obs,(SimpleNamespace(asset=asset),))


@pytest.mark.asyncio
async def test_candidate_fetch_verification_updates_graph_but_not_existing_daily_state(tmp_path):
    scenario=runpy.run_path("tests/ausi/fixtures/ai_daily_candidate_verification_scenario.py")["build_scenario"]()
    store=KnowledgeStore(tmp_path/"knowledge.db")
    try:
        fetched=build_ai_daily_from_fetched_pages(store=store,batch_id="batch:verify",observation=scenario.observation,fetched_pages=scenario.fetched_pages,source_nodes=scenario.source_nodes,claim_keywords=("Model X","release"),claim_draft=scenario.claim_draft,evidence_source_ids=scenario.evidence_source_ids,event_draft=scenario.event_draft,state=scenario.state,budget=scenario.budget,policy=scenario.policy,generated_at=scenario.state.as_of,artifact_id="artifact:verify:zh",importance=0.98,freshness=1.0,audience_relevance=0.95,confidence=0.99)
        assert fetched.discovery_result.canonical_claim.independent_root_count==3
        search_registry=_registry(LEXICAL_METHOD,"provider.search","surface.search","binding.search","capability.lexical")
        search_ctx=ExecutionContext("task:verify","epoch:verify","snap",services={})
        search_policy=PolicyContext("task:verify","research",None,RiskClass.LOW,(),(AcquisitionAction.AUTOMATED_QUERY,),scenario.state.as_of)
        expanded=await expand_ai_daily_reverse_trace(fetched,providers=search_registry,trusted_runtime=SearchRuntime(),execution_context=search_ctx,policy_context=search_policy,task_id="task:verify",epoch_id="epoch:verify",created_at=scenario.state.as_of)
        fetch_registry=_registry(FETCH_METHOD,"provider.fetch","surface.fetch","binding.fetch","capability.fetch_url")
        html_by_url={page.url:page.html for page in scenario.fetched_pages}
        fetch_ctx=ExecutionContext("task:verify","epoch:fetch","snap",services={})
        fetch_policy=PolicyContext("task:verify","research",None,RiskClass.LOW,(),(AcquisitionAction.FETCH,),scenario.state.as_of)
        verified=await verify_ai_daily_reverse_trace(expanded,source_nodes=scenario.source_nodes,tracked_source_ids=scenario.evidence_source_ids,providers=fetch_registry,trusted_runtime=FetchRuntime(html_by_url),execution_context=fetch_ctx,policy_context=fetch_policy,reader=lambda ref: html_by_url[ref.removeprefix("mem:")],task_id="task:verify",epoch_id="epoch:fetch",created_at=scenario.state.as_of)
    finally:
        store.close()
    update=verified.verification_update
    assert update.independent_root_count_before==3
    assert update.independent_root_count_after==2
    inferred=[r for r in update.verified_relations if r.inference_type.value=="inferred"]
    assert len(inferred)==1 and inferred[0].to_source_id=="source:https://official.example/model-x"
    statuses=[rec.verification.status for b in update.batches for rec in b.records if rec.verification]
    assert PredecessorVerificationStatus.RELATED_ONLY in statuses
    assert verified.reverse_trace_result.fetched_result.discovery_result.canonical_claim.independent_root_count==3
    assert verified.reverse_trace_result.fetched_result.discovery_result.mvp_result.zh_hant_artifact.knowledge_state_id==scenario.state.state_id
