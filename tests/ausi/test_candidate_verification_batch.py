from types import SimpleNamespace

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, VersionRef
from ai_web_research.discovery.models import DiscoveryBatch, DiscoveryCandidate
from ai_web_research.evidence.models import AcquiredAsset
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.candidate_verification import FETCH_METHOD
from ai_web_research.source_graph.predecessor_verification import PredecessorVerificationStatus
from ai_web_research.source_graph.candidate_batch import verify_trace_candidate_batches
from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.html_extract import extract_page_source_signals
from ai_web_research.source_graph.signal_compile import compile_page_source_signals
from ai_web_research.source_graph.models import SourceNode
from ai_web_research.source_graph.trace import plan_reverse_trace
from ai_web_research.source_graph.trace_execution import TraceExecutionBatch, TraceExecutionStatus, TraceSearchExecution
from ai_web_research.domains.ai_industry.live_discovery import FetchedSourcePageResult


def _page(url, html):
    return FetchedPage(f"source:{url}", url, None, html, "2026-09-02T00:00:00Z", None, None, None, None, url, False)


def _source_result(url, html):
    page=_page(url,html); ext=extract_page_source_signals(page); comp=compile_page_source_signals(page,ext,claim_keywords=("Model X",)); return FetchedSourcePageResult(page,ext,comp)


def _candidate(url, rank, cid):
    return DiscoveryCandidate(cid,url,None,None,"provider.search","surface.search",rank,(cid,),{"evidence_role":"discovery_only"})


def _trace_execution(source_id, trace_id, kind, candidates):
    return TraceSearchExecution(source_id,trace_id,kind,f"search:{trace_id}","provider.search","binding.search",TraceExecutionStatus.SUCCEEDED,DiscoveryBatch(f"obs:{trace_id}","q",tuple(candidates),"provider.search","2026-09-02T00:00:00Z"),f"obs:{trace_id}",None)


def _providers():
    provider=ProviderSpec("provider.fetch","1.0.0",ProviderKind.CRAWLER,"Fetch",(),(),(),(ProviderSurface("surface.fetch",SurfaceKind.PUBLIC_API,None,frozenset({"capability.fetch_url"}),None,(),{},{}),),{})
    binding=MethodBinding("binding.fetch",FETCH_METHOD,VersionRef("provider.fetch","1.0.0"),"surface.fetch","adapter.fetch","1.0.0",True,{}, {})
    return ProviderRegistrySnapshot("snap",(provider,),(binding,))


def _contexts():
    return ExecutionContext("task:1","epoch:1","snap",services={}), PolicyContext("task:1","research",None,RiskClass.LOW,(),(AcquisitionAction.FETCH,),"2026-09-02T00:00:00Z")


class Runtime:
    def __init__(self, pages, fail_urls=()): self.pages=pages; self.fail_urls=set(fail_urls); self.calls=[]
    async def execute(self, action, *args, **kwargs):
        url=action.parameters["url"]; self.calls.append(url)
        if url in self.fail_urls: raise RuntimeError("fetch failed")
        artifact=ArtifactRef(ArtifactKind.DOCUMENT,f"doc:{url}",metadata={"url":url,"fetched_at":"2026-09-02T00:00:01Z"})
        asset=AcquiredAsset(f"asset:{url}",f"obs:{url}","provider.fetch","surface.fetch",artifact,f"mem:{url}","text/html","2026-09-02T00:00:01Z",None,"usage","acq")
        return SimpleNamespace(observation=SimpleNamespace(observation_id=f"obs:{url}"),materialized_assets=(SimpleNamespace(asset=asset),))


def _node(page):
    return SourceNode(page.source_id,page.url,None,None,page.observed_at,None,None,{})


@pytest.mark.asyncio
async def test_batch_deduplicates_orders_limits_and_preserves_sibling_on_failure():
    from ai_web_research.source_graph.trace import TraceActionKind
    source=_source_result("https://media.example/story",'<p>According to <a href="https://direct.example/source">Direct</a>.</p><q>A distinctive quote about Model X source.</q>')
    plan=plan_reverse_trace(source.page.source_id,source.compiled.trace_signals)
    quote_action=next(a for a in plan.actions if a.kind is TraceActionKind.EXACT_QUOTE_SEARCH)
    executions=(
        _trace_execution(source.page.source_id,quote_action.action_id,quote_action.kind,(
            _candidate("https://b.example/",2,"b"),
            _candidate("https://a.example/",1,"a"),
            _candidate("https://a.example/",3,"a-dup"),
        )),
    )
    batch=TraceExecutionBatch(source.page.source_id,executions,tuple(a.action_id for a in plan.actions if a.kind is TraceActionKind.DIRECT_PREDECESSOR),True)
    pages={"https://direct.example/source":"<p>direct</p>","https://a.example/":"<p>a</p>","https://b.example/":"<p>b</p>"}
    runtime=Runtime(pages,fail_urls={"https://a.example/"}); execution,policy=_contexts()
    result=await verify_trace_candidate_batches(
        source_page_results=(source,),trace_plans={source.page.source_id:plan},trace_execution_batches=(batch,),
        source_nodes=(_node(source.page),),source_relations=(),tracked_source_ids=(source.page.source_id,),
        providers=_providers(),trusted_runtime=runtime,execution_context=execution,policy_context=policy,
        reader=lambda ref: pages[ref.removeprefix("mem:")],task_id="task:1",epoch_id="epoch:1",created_at="2026-09-02T00:00:00Z",
        max_candidates_per_execution=2,max_total_candidate_fetches=2,
    )
    assert runtime.calls == ["https://direct.example/source", "https://a.example/"]
    assert result.batches[0].complete is False
    assert len(result.batches[0].records) == 2
    assert result.batches[0].records[0].fetch.status.value == "fetched"
    assert result.batches[0].records[1].fetch.status.value == "provider_failed"


@pytest.mark.asyncio
async def test_verified_inferred_relation_recomputes_family_root_count():
    from ai_web_research.source_graph.trace import TraceActionKind, ReverseTracePlan
    phrase="Model X is available today with a new reasoning mode."
    media_a=_source_result("https://media.example/a",f'<p>According to <a href="https://official.example/about">Official Example</a>:</p><q>{phrase}</q>')
    media_b=_source_result("https://media.example/b",'<link rel="syndication-source" href="https://media.example/a">')
    official=_page("https://official.example/model-x",f'<meta property="og:site_name" content="Official Example"><p>{phrase}</p>')
    repo=_page("https://repo.example/model-x",'<meta property="og:site_name" content="Official Example"><p>Different content.</p>')
    nodes=(_node(media_a.page),_node(media_b.page),_node(official),_node(repo))
    relations=media_b.compiled.relations
    plan0=plan_reverse_trace(media_a.page.source_id,media_a.compiled.trace_signals)
    quote=next(a for a in plan0.actions if a.kind is TraceActionKind.EXACT_QUOTE_SEARCH)
    entity=next(a for a in plan0.actions if a.kind is TraceActionKind.ENTITY_SEARCH)
    plan=ReverseTracePlan(media_a.page.source_id,(quote,entity),False,None)
    batch=TraceExecutionBatch(media_a.page.source_id,(
        _trace_execution(media_a.page.source_id,quote.action_id,quote.kind,(_candidate(official.url,1,"official"),)),
        _trace_execution(media_a.page.source_id,entity.action_id,entity.kind,(_candidate(repo.url,1,"repo"),)),
    ),(),True)
    pages={official.url:official.html,repo.url:repo.html}; runtime=Runtime(pages); execution,policy=_contexts()
    result=await verify_trace_candidate_batches(
        source_page_results=(media_a,media_b),trace_plans={media_a.page.source_id:plan},trace_execution_batches=(batch,),
        source_nodes=nodes,source_relations=relations,tracked_source_ids=tuple(n.source_id for n in nodes),
        providers=_providers(),trusted_runtime=runtime,execution_context=execution,policy_context=policy,
        reader=lambda ref: pages[ref.removeprefix("mem:")],task_id="task:1",epoch_id="epoch:1",created_at="2026-09-02T00:00:00Z",
    )
    assert result.independent_root_count_before == 3
    assert result.independent_root_count_after == 2
    verified=[r for r in result.verified_relations if r.from_source_id==media_a.page.source_id]
    assert len(verified)==1
    assert verified[0].to_source_id==official.source_id
    statuses=[record.verification.status for b in result.batches for record in b.records if record.verification]
    assert PredecessorVerificationStatus.VERIFIED_INFERRED in statuses
    assert PredecessorVerificationStatus.RELATED_ONLY in statuses
