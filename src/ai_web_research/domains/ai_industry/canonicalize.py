from __future__ import annotations

from ai_web_research.knowledge.models import CanonicalClaim, CanonicalEvent, ClaimOrigin

from .models import ClaimDraft, EventDraft


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def promote_claim(draft: ClaimDraft) -> CanonicalClaim:
    evidence_ids = _unique(tuple(item.candidate_evidence_id for item in draft.evidence))
    if draft.claim_origin is ClaimOrigin.SOURCE_ASSERTION and not evidence_ids:
        raise ValueError("source assertion requires evidence")
    return CanonicalClaim(
        claim_id=draft.claim_id,
        revision=1,
        statement=draft.statement,
        subject_id=draft.subject_id,
        predicate=draft.predicate,
        object_value=draft.object_value,
        state=draft.state,
        claim_origin=draft.claim_origin,
        evidence_ids=evidence_ids,
        independent_root_count=draft.independent_root_count,
        known_at=draft.known_at,
        valid_time=draft.valid_time,
        metadata=draft.metadata,
    )


def canonicalize_event(draft: EventDraft) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=draft.event_id,
        revision=1,
        event_type=draft.event_type.value,
        entity_ids=_unique(draft.entity_ids),
        status=draft.status,
        claim_ids=_unique(draft.claim_ids),
        evidence_ids=_unique(draft.evidence_ids),
        known_at=draft.known_at,
        valid_time=draft.valid_time,
        metadata=draft.metadata,
    )
