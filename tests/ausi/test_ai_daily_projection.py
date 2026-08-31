from ai_web_research.domains.ai_industry.daily import DailyBatch
from ai_web_research.knowledge.models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimOrigin,
    ClaimState,
    EventStatus,
)
from ai_web_research.projection.daily import render_machine_daily, render_zh_hant_daily
from ai_web_research.projection.registry import ArtifactRegistry
from ai_web_research.resource_control.models import AnytimeStatus


NOW = "2026-08-31T12:00:00Z"


def _claim(claim_id: str, state: ClaimState, statement: str) -> CanonicalClaim:
    return CanonicalClaim(
        claim_id=claim_id,
        revision=1,
        statement=statement,
        subject_id="model:model-x",
        predicate="status",
        object_value=True,
        state=state,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence_ids=(f"ev:{claim_id}",),
        independent_root_count=1,
        known_at=NOW,
        valid_time=None,
        metadata={},
    )


def _event(event_id: str, status: EventStatus, claim_id: str, event_type: str = "model_release") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        revision=1,
        event_type=event_type,
        entity_ids=("model:model-x",),
        status=status,
        claim_ids=(claim_id,),
        evidence_ids=(f"ev:{claim_id}",),
        known_at=NOW,
        valid_time=None,
        metadata={},
    )


def _batch(*, selected=(), watch=()) -> DailyBatch:
    return DailyBatch(
        batch_id="batch:daily",
        knowledge_state_id="Ksys:daily",
        selected_event_ids=tuple(selected),
        watch_event_ids=tuple(watch),
        complete=True,
        anytime_status=AnytimeStatus.COMPLETE,
        stop_reason=None,
        open_event_ids=(),
        generated_at=NOW,
    )


def test_zh_projection_preserves_confirmed_and_well_supported_status_with_lineage():
    confirmed = _claim("claim:confirmed", ClaimState.CONFIRMED, "Model X 已正式發布。")
    supported = _claim("claim:supported", ClaimState.WELL_SUPPORTED, "Model Y 已公開技術報告。")
    e1 = _event("evt:confirmed", EventStatus.CONFIRMED, confirmed.claim_id)
    e2 = _event("evt:supported", EventStatus.CONFIRMED, supported.claim_id, "paper_release")

    artifact = render_zh_hant_daily(
        artifact_id="artifact:zh",
        batch=_batch(selected=(e1.event_id, e2.event_id)),
        events={e1.event_id: e1, e2.event_id: e2},
        claims={confirmed.claim_id: confirmed, supported.claim_id: supported},
        generated_at=NOW,
    )

    assert artifact.knowledge_state_id == "Ksys:daily"
    assert [unit.status_label for unit in artifact.units] == ["已確認", "多方支持"]
    assert artifact.units[0].claim_ids == (confirmed.claim_id,)
    assert artifact.units[0].event_ids == (e1.event_id,)
    assert "[已確認] Model X 已正式發布。" in artifact.metadata["script_text"]


def test_watch_projection_keeps_unverified_label_and_separate_heading():
    rumor = _claim("claim:rumor", ClaimState.UNVERIFIED, "Model X 可能明天推出新版本。")
    event = _event("evt:rumor", EventStatus.CANDIDATE, rumor.claim_id, "rumor_detected")

    artifact = render_zh_hant_daily(
        artifact_id="artifact:watch",
        batch=_batch(watch=(event.event_id,)),
        events={event.event_id: event},
        claims={rumor.claim_id: rumor},
        generated_at=NOW,
    )

    assert artifact.units[0].status_label == "尚未確認"
    assert "值得追蹤（尚未確認）" in artifact.metadata["script_text"]
    assert "[尚未確認]" in artifact.metadata["script_text"]


def test_projection_never_upgrades_disputed_claim():
    disputed = _claim("claim:disputed", ClaimState.DISPUTED, "Model Z 的 benchmark 結果存在衝突。")
    event = _event("evt:disputed", EventStatus.DISPUTED, disputed.claim_id, "benchmark_result")

    artifact = render_zh_hant_daily(
        artifact_id="artifact:disputed",
        batch=_batch(selected=(event.event_id,)),
        events={event.event_id: event},
        claims={disputed.claim_id: disputed},
        generated_at=NOW,
    )

    assert artifact.units[0].status_label == "資訊有爭議"
    assert "已確認" not in artifact.metadata["script_text"]


def test_machine_projection_is_json_serializable_and_shares_batch_state_lineage():
    claim = _claim("claim:confirmed", ClaimState.CONFIRMED, "Model X released.")
    event = _event("evt:confirmed", EventStatus.CONFIRMED, claim.claim_id)
    batch = _batch(selected=(event.event_id,))

    payload = render_machine_daily(
        batch=batch,
        events={event.event_id: event},
        claims={claim.claim_id: claim},
    )

    assert payload["batch_id"] == batch.batch_id
    assert payload["knowledge_state_id"] == batch.knowledge_state_id
    assert payload["units"][0]["claim_ids"] == [claim.claim_id]
    assert payload["units"][0]["event_ids"] == [event.event_id]
    assert payload["units"][0]["claim_state"] == "confirmed"


def test_artifact_registry_returns_all_artifacts_affected_by_claim():
    claim = _claim("claim:confirmed", ClaimState.CONFIRMED, "Model X released.")
    event = _event("evt:confirmed", EventStatus.CONFIRMED, claim.claim_id)
    batch = _batch(selected=(event.event_id,))
    a1 = render_zh_hant_daily(
        artifact_id="artifact:b",
        batch=batch,
        events={event.event_id: event},
        claims={claim.claim_id: claim},
        generated_at=NOW,
    )
    a2 = render_zh_hant_daily(
        artifact_id="artifact:a",
        batch=batch,
        events={event.event_id: event},
        claims={claim.claim_id: claim},
        generated_at=NOW,
    )

    registry = ArtifactRegistry()
    registry.register(a1)
    registry.register(a2)
    impact = registry.affected_by_claim(claim.claim_id)

    assert impact.claim_id == claim.claim_id
    assert impact.artifact_ids == ("artifact:a", "artifact:b")
