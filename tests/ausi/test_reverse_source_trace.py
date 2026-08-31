from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.source_graph.models import SourceNode, SourceRelationType, RelationInferenceType
from ai_web_research.source_graph.trace import (
    SourceTraceSignals,
    TraceActionKind,
    plan_reverse_trace,
    materialize_explicit_trace_edges,
)


def source(sid='media_a', url='https://media.example/a'):
    return SourceNode(sid, url, None, None, '2026-08-31T15:00:00Z', None, None, {})


def candidate(cid, url, rank=1):
    return DiscoveryCandidate(
        candidate_id=cid,
        url=url,
        title=None,
        snippet=None,
        provider_id='provider.brave_search',
        surface_id='surface.brave_search.web',
        provider_rank=rank,
        artifact_ids=(cid,),
        metadata={'evidence_role': 'discovery_only'},
    )


def test_explicit_attributed_url_produces_direct_predecessor_action():
    signals = SourceTraceSignals(
        attributed_source_urls=('https://official.example/release',),
        attribution_entities=(),
        quoted_phrases=(),
        claim_keywords=('Model X', 'release'),
    )
    plan = plan_reverse_trace('media_a', signals)
    assert plan.unresolved is False
    assert plan.actions[0].kind is TraceActionKind.DIRECT_PREDECESSOR
    assert plan.actions[0].url == 'https://official.example/release'
    assert plan.actions[0].query is None


def test_quote_and_entity_signals_create_provider_neutral_search_actions():
    signals = SourceTraceSignals(
        attributed_source_urls=(),
        attribution_entities=('Company Y',),
        quoted_phrases=('a rare exact phrase',),
        claim_keywords=('Model X', 'release'),
    )
    plan = plan_reverse_trace('media_a', signals)
    kinds = [action.kind for action in plan.actions]
    assert kinds == [TraceActionKind.EXACT_QUOTE_SEARCH, TraceActionKind.ENTITY_SEARCH]
    assert plan.actions[0].query == '"a rare exact phrase"'
    assert plan.actions[1].query == '"Company Y" Model X release'
    assert all(not hasattr(action, 'provider_id') for action in plan.actions)


def test_no_signals_remains_explicitly_unresolved():
    plan = plan_reverse_trace('media_a', SourceTraceSignals((), (), (), ()))
    assert plan.actions == ()
    assert plan.unresolved is True
    assert plan.reason == 'no_trace_signals'


def test_provider_rank_alone_never_materializes_dependency_edge():
    edges = materialize_explicit_trace_edges(
        source(),
        (candidate('c1', 'https://official.example/release', rank=1),),
        SourceTraceSignals((), (), (), ('Model X',)),
    )
    assert edges == ()


def test_exact_attributed_url_materializes_explicit_dependency_edge():
    signals = SourceTraceSignals(
        attributed_source_urls=('https://official.example/release/',),
        attribution_entities=(),
        quoted_phrases=(),
        claim_keywords=('Model X',),
    )
    edges = materialize_explicit_trace_edges(
        source(),
        (candidate('c1', 'https://official.example/release', rank=9),),
        signals,
    )
    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_source_id == 'media_a'
    assert edge.to_source_id == 'source:https://official.example/release'
    assert edge.relation_type is SourceRelationType.DERIVED_FROM
    assert edge.inference_type is RelationInferenceType.EXPLICIT
    assert edge.confidence == 1.0
    assert 'explicit_attributed_url' in edge.signals
