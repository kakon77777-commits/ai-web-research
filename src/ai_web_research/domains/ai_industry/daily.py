from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.knowledge.models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimState,
    EventStatus,
    KnowledgeState,
)
from ai_web_research.resource_control.models import AnytimeStatus, ResearchBudget


_MAIN_CLAIM_STATES = {ClaimState.WELL_SUPPORTED, ClaimState.CONFIRMED}


@dataclass(frozen=True)
class DailySelectionPolicy:
    include_what_to_watch: bool = False


@dataclass(frozen=True)
class DailyEventInput:
    event: CanonicalEvent
    claims: tuple[CanonicalClaim, ...]
    importance: float
    freshness: float
    audience_relevance: float
    confidence: float

    def __post_init__(self) -> None:
        for name in ("importance", "freshness", "audience_relevance", "confidence"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    @property
    def score(self) -> float:
        return (
            0.35 * self.importance
            + 0.25 * self.freshness
            + 0.20 * self.audience_relevance
            + 0.20 * self.confidence
        )


@dataclass(frozen=True)
class DailyBatch:
    batch_id: str
    knowledge_state_id: str
    selected_event_ids: tuple[str, ...]
    watch_event_ids: tuple[str, ...]
    complete: bool
    anytime_status: AnytimeStatus
    stop_reason: str | None
    open_event_ids: tuple[str, ...]
    generated_at: str


def _main_eligible(item: DailyEventInput) -> bool:
    return (
        item.event.status is EventStatus.CONFIRMED
        and bool(item.claims)
        and all(claim.state in _MAIN_CLAIM_STATES for claim in item.claims)
    )


def _watch_eligible(item: DailyEventInput) -> bool:
    return (
        item.event.event_type == "rumor_detected"
        and item.event.status is EventStatus.CANDIDATE
        and bool(item.claims)
        and all(claim.state is ClaimState.UNVERIFIED for claim in item.claims)
    )


def _rank(items: list[DailyEventInput]) -> list[DailyEventInput]:
    return sorted(items, key=lambda item: (-item.score, item.event.event_id))


def select_daily_batch(
    *,
    batch_id: str,
    state: KnowledgeState,
    candidates: tuple[DailyEventInput, ...],
    budget: ResearchBudget,
    policy: DailySelectionPolicy,
    generated_at: str,
) -> DailyBatch:
    allowed_event_ids = set(state.event_ids)
    scoped = [item for item in candidates if item.event.event_id in allowed_event_ids]

    main = _rank([item for item in scoped if _main_eligible(item)])
    watch = _rank(
        [item for item in scoped if _watch_eligible(item)]
        if policy.include_what_to_watch
        else []
    )

    selected = main[: budget.max_selected_events]
    selected_watch = watch[: budget.max_watch_events]
    deferred = main[budget.max_selected_events :] + watch[budget.max_watch_events :]
    open_event_ids = tuple(item.event.event_id for item in deferred)
    complete = not open_event_ids

    return DailyBatch(
        batch_id=batch_id,
        knowledge_state_id=state.state_id,
        selected_event_ids=tuple(item.event.event_id for item in selected),
        watch_event_ids=tuple(item.event.event_id for item in selected_watch),
        complete=complete,
        anytime_status=AnytimeStatus.COMPLETE if complete else AnytimeStatus.PARTIAL,
        stop_reason=None if complete else "budget_exhausted",
        open_event_ids=open_event_ids,
        generated_at=generated_at,
    )
