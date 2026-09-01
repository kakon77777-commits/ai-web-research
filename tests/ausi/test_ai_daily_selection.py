from ai_web_research.domains.ai_industry.daily import (
    DailyEventInput,
    DailySelectionPolicy,
    select_daily_batch,
)
from ai_web_research.knowledge.models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimOrigin,
    ClaimState,
    EventStatus,
    KnowledgeMode,
    KnowledgeState,
)
from ai_web_research.resource_control.models import AnytimeStatus, ResearchBudget


NOW = "2026-08-31T12:00:00Z"


def _claim(claim_id: str, state: ClaimState, *, statement: str | None = None) -> CanonicalClaim:
    return CanonicalClaim(
        claim_id=claim_id,
        revision=1,
        statement=statement or claim_id,
        subject_id="model:model-x",
        predicate="released",
        object_value=True,
        state=state,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence_ids=(f"ev:{claim_id}",),
        independent_root_count=1,
        known_at=NOW,
        valid_time=None,
        metadata={},
    )


def _event(event_id: str, status: EventStatus, claim_id: str, *, event_type: str = "model_release") -> CanonicalEvent:
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


def _state(*event_ids: str) -> KnowledgeState:
    return KnowledgeState(
        state_id="Ksys:daily",
        mode=KnowledgeMode.SYSTEM_AS_KNOWN,
        as_of=NOW,
        policy_version="ai-daily-v1",
        claim_ids=tuple(f"claim:{event_id}" for event_id in event_ids),
        event_ids=event_ids,
        metadata={},
    )


def test_main_brief_requires_confirmed_event_and_supported_claim():
    confirmed_claim = _claim("claim:confirmed", ClaimState.CONFIRMED)
    weak_claim = _claim("claim:weak", ClaimState.UNVERIFIED)
    confirmed_event = _event("evt:confirmed", EventStatus.CONFIRMED, confirmed_claim.claim_id)
    weak_event = _event("evt:weak", EventStatus.CONFIRMED, weak_claim.claim_id)

    batch = select_daily_batch(
        batch_id="batch:1",
        state=_state(confirmed_event.event_id, weak_event.event_id),
        candidates=(
            DailyEventInput(confirmed_event, (confirmed_claim,), 0.8, 0.8, 0.8, 0.8),
            DailyEventInput(weak_event, (weak_claim,), 1.0, 1.0, 1.0, 1.0),
        ),
        budget=ResearchBudget(max_selected_events=5, max_watch_events=0),
        policy=DailySelectionPolicy(),
        generated_at=NOW,
    )

    assert batch.selected_event_ids == ("evt:confirmed",)
    assert batch.watch_event_ids == ()
    assert batch.complete is True
    assert batch.anytime_status is AnytimeStatus.COMPLETE


def test_unverified_rumor_is_only_allowed_in_labeled_watch_section():
    rumor_claim = _claim("claim:rumor", ClaimState.UNVERIFIED, statement="Model X may launch tomorrow.")
    rumor_event = _event(
        "evt:rumor",
        EventStatus.CANDIDATE,
        rumor_claim.claim_id,
        event_type="rumor_detected",
    )
    candidate = DailyEventInput(rumor_event, (rumor_claim,), 0.9, 1.0, 0.8, 0.3)

    hidden = select_daily_batch(
        batch_id="batch:hidden",
        state=_state(rumor_event.event_id),
        candidates=(candidate,),
        budget=ResearchBudget(max_selected_events=5, max_watch_events=5),
        policy=DailySelectionPolicy(include_what_to_watch=False),
        generated_at=NOW,
    )
    visible = select_daily_batch(
        batch_id="batch:visible",
        state=_state(rumor_event.event_id),
        candidates=(candidate,),
        budget=ResearchBudget(max_selected_events=5, max_watch_events=5),
        policy=DailySelectionPolicy(include_what_to_watch=True),
        generated_at=NOW,
    )

    assert hidden.selected_event_ids == ()
    assert hidden.watch_event_ids == ()
    assert visible.selected_event_ids == ()
    assert visible.watch_event_ids == ("evt:rumor",)


def test_score_order_is_deterministic_with_event_id_tiebreak():
    claim_a = _claim("claim:a", ClaimState.WELL_SUPPORTED)
    claim_b = _claim("claim:b", ClaimState.WELL_SUPPORTED)
    event_a = _event("evt:a", EventStatus.CONFIRMED, claim_a.claim_id)
    event_b = _event("evt:b", EventStatus.CONFIRMED, claim_b.claim_id)

    equal = dict(importance=0.8, freshness=0.7, audience_relevance=0.6, confidence=0.9)
    batch = select_daily_batch(
        batch_id="batch:tie",
        state=_state(event_b.event_id, event_a.event_id),
        candidates=(
            DailyEventInput(event_b, (claim_b,), **equal),
            DailyEventInput(event_a, (claim_a,), **equal),
        ),
        budget=ResearchBudget(max_selected_events=2, max_watch_events=0),
        policy=DailySelectionPolicy(),
        generated_at=NOW,
    )

    assert batch.selected_event_ids == ("evt:a", "evt:b")


def test_budget_truncation_returns_usable_partial_batch_and_open_event_ids():
    claims = tuple(_claim(f"claim:{i}", ClaimState.CONFIRMED) for i in range(3))
    events = tuple(_event(f"evt:{i}", EventStatus.CONFIRMED, claims[i].claim_id) for i in range(3))
    candidates = tuple(
        DailyEventInput(
            events[i],
            (claims[i],),
            importance=1.0 - i * 0.1,
            freshness=1.0,
            audience_relevance=1.0,
            confidence=1.0,
        )
        for i in range(3)
    )

    batch = select_daily_batch(
        batch_id="batch:bounded",
        state=_state(*(event.event_id for event in events)),
        candidates=candidates,
        budget=ResearchBudget(max_selected_events=1, max_watch_events=0),
        policy=DailySelectionPolicy(),
        generated_at=NOW,
    )

    assert batch.selected_event_ids == ("evt:0",)
    assert batch.complete is False
    assert batch.anytime_status is AnytimeStatus.PARTIAL
    assert batch.stop_reason == "budget_exhausted"
    assert batch.open_event_ids == ("evt:1", "evt:2")
