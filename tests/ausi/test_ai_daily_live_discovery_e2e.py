import runpy

from ai_web_research.domains.ai_industry.live_discovery import build_ai_daily_from_discovery
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.source_graph.trace import TraceActionKind

_fixture = runpy.run_path('tests/ausi/fixtures/ai_daily_live_discovery_scenario.py')
build_scenario = _fixture['build_scenario']


def test_live_discovery_to_canonical_daily_projection(tmp_path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / 'knowledge.db')
    try:
        result = build_ai_daily_from_discovery(
            store=store,
            batch_id='batch:live:001',
            observation=scenario.observation,
            source_nodes=scenario.source_nodes,
            base_relations=scenario.base_relations,
            trace_signals_by_source=scenario.trace_signals_by_source,
            claim_draft=scenario.claim_draft,
            evidence_source_ids=scenario.evidence_source_ids,
            event_draft=scenario.event_draft,
            state=scenario.state,
            budget=scenario.budget,
            policy=scenario.policy,
            generated_at=scenario.state.as_of,
            artifact_id='artifact:live:zh',
            importance=0.98,
            freshness=1.0,
            audience_relevance=0.95,
            confidence=0.99,
        )
    finally:
        store.close()

    assert len(result.discovery_batch.candidates) == 4
    assert all(c.metadata['evidence_role'] == 'discovery_only' for c in result.discovery_batch.candidates)
    assert all('Brave snippet' not in eid for eid in result.canonical_claim.evidence_ids)

    media_plan = next(iter(result.trace_plans.values()))
    assert TraceActionKind.EXACT_QUOTE_SEARCH in {a.kind for a in media_plan.actions}
    assert TraceActionKind.ENTITY_SEARCH in {a.kind for a in media_plan.actions}

    assert result.family_resolution.independent_root_count(scenario.evidence_source_ids) == 2
    assert result.canonical_claim.independent_root_count == 2
    assert result.canonical_event.event_id == 'evt:model-x-release-live'
    assert result.mvp_result.batch.selected_event_ids == ('evt:model-x-release-live',)

    machine = result.mvp_result.machine_projection
    zh = result.mvp_result.zh_hant_artifact
    assert machine['knowledge_state_id'] == zh.knowledge_state_id == scenario.state.state_id
    assert machine['units'][0]['status_label'] == '已確認'
    assert '[已確認] Model X 已正式發布。' in zh.metadata['script_text']


def test_only_explicit_attribution_and_given_syndication_create_dependencies(tmp_path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / 'knowledge.db')
    try:
        result = build_ai_daily_from_discovery(
            store=store,
            batch_id='batch:live:002',
            observation=scenario.observation,
            source_nodes=scenario.source_nodes,
            base_relations=scenario.base_relations,
            trace_signals_by_source=scenario.trace_signals_by_source,
            claim_draft=scenario.claim_draft,
            evidence_source_ids=scenario.evidence_source_ids,
            event_draft=scenario.event_draft,
            state=scenario.state,
            budget=scenario.budget,
            policy=scenario.policy,
            generated_at=scenario.state.as_of,
            artifact_id='artifact:live:zh2',
            importance=0.98,
            freshness=1.0,
            audience_relevance=0.95,
            confidence=0.99,
        )
    finally:
        store.close()

    relation_ids = {relation.relation_id for relation in result.source_relations}
    assert 'rel:media-b-syndicated-media-a' in relation_ids
    explicit_trace = [r for r in result.source_relations if 'explicit_attributed_url' in r.signals]
    assert len(explicit_trace) == 1
    assert len(result.source_relations) == 2
