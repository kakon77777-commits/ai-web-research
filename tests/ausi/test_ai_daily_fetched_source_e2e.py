import runpy

from ai_web_research.domains.ai_industry.live_discovery import build_ai_daily_from_fetched_pages
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.source_graph.models import SourceRelationType
from ai_web_research.source_graph.page_signals import PageSourceSignalKind

_fixture = runpy.run_path("tests/ausi/fixtures/ai_daily_fetched_source_scenario.py")
build_scenario = _fixture["build_scenario"]


def test_fetched_pages_derive_source_lineage_and_daily_projection(tmp_path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        result = build_ai_daily_from_fetched_pages(
            store=store, batch_id="batch:fetched:001", observation=scenario.observation,
            fetched_pages=scenario.fetched_pages, source_nodes=scenario.source_nodes,
            claim_keywords=("Model X", "release"), claim_draft=scenario.claim_draft,
            evidence_source_ids=scenario.evidence_source_ids, event_draft=scenario.event_draft,
            state=scenario.state, budget=scenario.budget, policy=scenario.policy,
            generated_at=scenario.state.as_of, artifact_id="artifact:fetched:zh",
            importance=0.98, freshness=1.0, audience_relevance=0.95, confidence=0.99,
        )
    finally:
        store.close()

    by_source = {item.page.source_id: item for item in result.page_results}
    media_a = by_source["source:https://media.example/a"]
    media_b = by_source["source:https://media.example/b"]
    assert PageSourceSignalKind.ORIGINAL_SOURCE in {s.kind for s in media_a.extraction.signals}
    assert PageSourceSignalKind.QUOTED_PHRASE in {s.kind for s in media_a.extraction.signals}
    assert PageSourceSignalKind.SYNDICATION_SOURCE in {s.kind for s in media_b.extraction.signals}

    relation_types = [r.relation_type for r in result.discovery_result.source_relations]
    assert relation_types == [SourceRelationType.DERIVED_FROM, SourceRelationType.SYNDICATED_FROM]
    assert result.discovery_result.family_resolution.independent_root_count(scenario.evidence_source_ids) == 2
    assert result.discovery_result.canonical_claim.independent_root_count == 2

    machine = result.discovery_result.mvp_result.machine_projection
    zh = result.discovery_result.mvp_result.zh_hant_artifact
    assert machine["knowledge_state_id"] == zh.knowledge_state_id == scenario.state.state_id
    assert machine["units"][0]["status_label"] == "已確認"
    assert "[已確認] Model X 已正式發布。" in zh.metadata["script_text"]
    assert all("Brave snippet" not in eid for eid in result.discovery_result.canonical_claim.evidence_ids)


def test_fetched_page_wrapper_does_not_use_old_url_match_materializer(tmp_path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        result = build_ai_daily_from_fetched_pages(
            store=store, batch_id="batch:fetched:002", observation=scenario.observation,
            fetched_pages=scenario.fetched_pages, source_nodes=scenario.source_nodes,
            claim_keywords=("Model X", "release"), claim_draft=scenario.claim_draft,
            evidence_source_ids=scenario.evidence_source_ids, event_draft=scenario.event_draft,
            state=scenario.state, budget=scenario.budget, policy=scenario.policy,
            generated_at=scenario.state.as_of, artifact_id="artifact:fetched:zh2",
            importance=0.98, freshness=1.0, audience_relevance=0.95, confidence=0.99,
        )
    finally:
        store.close()

    relations = result.discovery_result.source_relations
    assert len(relations) == 2
    assert all("explicit_attributed_url" not in r.signals for r in relations)
