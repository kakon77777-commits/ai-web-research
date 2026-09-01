from dataclasses import replace
from pathlib import Path
import runpy

from ai_web_research.domains.ai_industry.daily import DailySelectionPolicy
from ai_web_research.domains.ai_industry.mvp import build_ai_daily_mvp
from ai_web_research.knowledge.models import ClaimState
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.resource_control.models import ResearchBudget


_fixture = runpy.run_path(Path(__file__).parent / "fixtures" / "ai_daily_release_scenario.py")
build_scenario = _fixture["build_scenario"]


def test_ai_daily_mvp_closes_the_canonical_vertical_slice(tmp_path: Path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        result = build_ai_daily_mvp(
            store=store,
            batch_id="batch:2026-08-31",
            claims=scenario.claims,
            events=scenario.events,
            state=scenario.state,
            candidates=scenario.candidates,
            budget=ResearchBudget(max_selected_events=1, max_watch_events=1),
            policy=DailySelectionPolicy(include_what_to_watch=True),
            generated_at=scenario.state.as_of,
            artifact_id="artifact:2026-08-31:zh",
            upstream_failures=("provider:temporary-failure",),
        )

        projected_claim_ids = {
            claim_id
            for unit in result.zh_hant_artifact.units
            for claim_id in unit.claim_ids
        }
        claims_by_id = {claim.claim_id: claim for claim in scenario.claims}
        for claim_id in projected_claim_ids:
            claim = claims_by_id[claim_id]
            assert claim.evidence_ids
            assert all(evidence_id in scenario.evidence_locators for evidence_id in claim.evidence_ids)

        release = claims_by_id[scenario.release_claim_id]
        assert len(release.evidence_ids) == 4
        assert release.independent_root_count == 2

        assert result.batch.selected_event_ids == (scenario.release_event_id,)
        assert result.batch.watch_event_ids == (scenario.rumor_event_id,)
        assert scenario.api_event_id not in result.batch.selected_event_ids
        assert scenario.api_event_id not in result.batch.watch_event_ids
        assert result.batch.complete is False
        assert result.batch.stop_reason == "budget_exhausted"
        assert "evt:model-x-paper" in result.batch.open_event_ids

        assert all(unit.claim_ids and unit.event_ids for unit in result.zh_hant_artifact.units)
        assert result.machine_projection["knowledge_state_id"] == scenario.state.state_id
        assert result.zh_hant_artifact.knowledge_state_id == scenario.state.state_id
        assert result.upstream_failures == ("provider:temporary-failure",)

        assert store.count_claim_revisions() == len(scenario.claims)
        assert store.count_event_revisions() == len(scenario.events)
    finally:
        store.close()


def test_later_claim_correction_locates_affected_daily_artifact(tmp_path: Path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        result = build_ai_daily_mvp(
            store=store,
            batch_id="batch:correction",
            claims=scenario.claims,
            events=scenario.events,
            state=scenario.state,
            candidates=scenario.candidates,
            budget=ResearchBudget(max_selected_events=1, max_watch_events=1),
            policy=DailySelectionPolicy(include_what_to_watch=True),
            generated_at=scenario.state.as_of,
            artifact_id="artifact:correction:zh",
        )
        original = store.get_latest_claim(scenario.release_claim_id)
        corrected = replace(
            original,
            revision=2,
            state=ClaimState.SUPERSEDED,
            statement="先前 License L1 敘述已被 repository 更新；最新證據指向 License L2。",
            known_at="2026-08-31T14:00:00Z",
        )
        store.save_claim(corrected)

        impact = result.artifact_registry.affected_by_claim(scenario.release_claim_id)
        assert impact.artifact_ids == ("artifact:correction:zh",)
        assert store.get_latest_claim(scenario.release_claim_id) == corrected
        assert len(store.list_claim_revisions(scenario.release_claim_id)) == 2
    finally:
        store.close()


def test_upstream_failure_marker_never_creates_canonical_objects(tmp_path: Path):
    scenario = build_scenario()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        before = (store.count_claim_revisions(), store.count_event_revisions())
        assert before == (0, 0)

        result = build_ai_daily_mvp(
            store=store,
            batch_id="batch:failure",
            claims=(),
            events=(),
            state=replace(scenario.state, state_id="Ksys:failure", claim_ids=(), event_ids=()),
            candidates=(),
            budget=ResearchBudget(max_selected_events=1, max_watch_events=1),
            policy=DailySelectionPolicy(include_what_to_watch=True),
            generated_at=scenario.state.as_of,
            artifact_id="artifact:failure:zh",
            upstream_failures=("provider:failed",),
        )

        assert result.upstream_failures == ("provider:failed",)
        assert store.count_claim_revisions() == 0
        assert store.count_event_revisions() == 0
        assert result.batch.selected_event_ids == ()
        assert result.zh_hant_artifact.units == ()
    finally:
        store.close()
