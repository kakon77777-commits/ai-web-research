from __future__ import annotations

from collections.abc import Mapping

from ai_web_research.domains.ai_industry.daily import DailyBatch
from ai_web_research.knowledge.models import CanonicalClaim, CanonicalEvent, ClaimState

from .models import ProjectionArtifact, ProjectionUnit


_STATUS_LABELS = {
    ClaimState.CONFIRMED: "已確認",
    ClaimState.WELL_SUPPORTED: "多方支持",
    ClaimState.PARTIALLY_SUPPORTED: "部分支持",
    ClaimState.UNVERIFIED: "尚未確認",
    ClaimState.OBSERVED: "尚待驗證",
    ClaimState.DISPUTED: "資訊有爭議",
    ClaimState.CONTRADICTED: "已被反證",
    ClaimState.SUPERSEDED: "已被更新",
    ClaimState.WITHDRAWN: "已撤回",
    ClaimState.RETRACTED: "已撤稿／撤回",
}


def _first_claim(event: CanonicalEvent, claims: Mapping[str, CanonicalClaim]) -> CanonicalClaim:
    for claim_id in event.claim_ids:
        claim = claims.get(claim_id)
        if claim is not None:
            return claim
    raise KeyError(f"no claim available for event {event.event_id}")


def _status_label(claim: CanonicalClaim) -> str:
    return _STATUS_LABELS[claim.state]


def _unit(event: CanonicalEvent, claim: CanonicalClaim, *, section: str, index: int) -> ProjectionUnit:
    return ProjectionUnit(
        unit_id=f"{section}:{index}:{event.event_id}",
        text=claim.statement,
        claim_ids=(claim.claim_id,),
        event_ids=(event.event_id,),
        status_label=_status_label(claim),
    )


def _iter_units(
    batch: DailyBatch,
    events: Mapping[str, CanonicalEvent],
    claims: Mapping[str, CanonicalClaim],
):
    for index, event_id in enumerate(batch.selected_event_ids):
        event = events[event_id]
        claim = _first_claim(event, claims)
        yield "main", _unit(event, claim, section="main", index=index), claim
    for index, event_id in enumerate(batch.watch_event_ids):
        event = events[event_id]
        claim = _first_claim(event, claims)
        yield "watch", _unit(event, claim, section="watch", index=index), claim


def render_machine_daily(
    *,
    batch: DailyBatch,
    events: Mapping[str, CanonicalEvent],
    claims: Mapping[str, CanonicalClaim],
) -> dict:
    units = []
    for section, unit, claim in _iter_units(batch, events, claims):
        units.append(
            {
                "unit_id": unit.unit_id,
                "section": section,
                "text": unit.text,
                "status_label": unit.status_label,
                "claim_state": claim.state.value,
                "claim_ids": list(unit.claim_ids),
                "event_ids": list(unit.event_ids),
            }
        )
    return {
        "batch_id": batch.batch_id,
        "knowledge_state_id": batch.knowledge_state_id,
        "selected_event_ids": list(batch.selected_event_ids),
        "watch_event_ids": list(batch.watch_event_ids),
        "complete": batch.complete,
        "stop_reason": batch.stop_reason,
        "open_event_ids": list(batch.open_event_ids),
        "generated_at": batch.generated_at,
        "units": units,
    }


def render_zh_hant_daily(
    *,
    artifact_id: str,
    batch: DailyBatch,
    events: Mapping[str, CanonicalEvent],
    claims: Mapping[str, CanonicalClaim],
    generated_at: str,
) -> ProjectionArtifact:
    all_units: list[ProjectionUnit] = []
    main_lines: list[str] = []
    watch_lines: list[str] = []

    for section, unit, _claim in _iter_units(batch, events, claims):
        all_units.append(unit)
        line = f"[{unit.status_label}] {unit.text}"
        if section == "watch":
            watch_lines.append(line)
        else:
            main_lines.append(line)

    sections: list[str] = []
    if main_lines:
        sections.append("今日 AI 重點\n" + "\n".join(main_lines))
    if watch_lines:
        sections.append("值得追蹤（尚未確認）\n" + "\n".join(watch_lines))
    script_text = "\n\n".join(sections)

    return ProjectionArtifact(
        artifact_id=artifact_id,
        channel="zh_hant_daily_script",
        knowledge_state_id=batch.knowledge_state_id,
        revision=1,
        units=tuple(all_units),
        generated_at=generated_at,
        metadata={"batch_id": batch.batch_id, "script_text": script_text},
    )
