from pathlib import Path

import pytest

from ai_web_research.knowledge.models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimOrigin,
    ClaimState,
    EventStatus,
    KnowledgeMode,
    KnowledgeState,
    ValidTime,
)
from ai_web_research.knowledge.sqlite import KnowledgeStore, KnowledgeStoreConflict


def _claim(*, revision: int = 1, state: ClaimState = ClaimState.CONFIRMED, statement: str = "Model X was released.") -> CanonicalClaim:
    return CanonicalClaim(
        claim_id="claim:model-x-release",
        revision=revision,
        statement=statement,
        subject_id="model:model-x",
        predicate="released",
        object_value=True,
        state=state,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence_ids=("ev:official-blog", "ev:official-repo"),
        independent_root_count=2,
        known_at="2026-08-31T09:05:00Z",
        valid_time=ValidTime(start="2026-08-31T09:00:00Z", end=None),
        metadata={"language": "en"},
    )


def _event(*, revision: int = 1, status: EventStatus = EventStatus.CONFIRMED) -> CanonicalEvent:
    return CanonicalEvent(
        event_id="evt:model-x-release",
        revision=revision,
        event_type="model_release",
        entity_ids=("model:model-x", "org:company-y"),
        status=status,
        claim_ids=("claim:model-x-release",),
        evidence_ids=("ev:official-blog", "ev:official-repo"),
        known_at="2026-08-31T09:05:00Z",
        valid_time=ValidTime(start="2026-08-31T09:00:00Z", end=None),
        metadata={"importance": 0.95},
    )


def test_store_appends_claim_revisions_and_returns_latest(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        v1 = _claim()
        v2 = _claim(revision=2, state=ClaimState.SUPERSEDED, statement="Model X release claim was superseded.")
        store.save_claim(v1)
        store.save_claim(v2)
        assert store.get_latest_claim(v1.claim_id) == v2
        assert store.list_claim_revisions(v1.claim_id) == (v1, v2)
    finally:
        store.close()


def test_store_appends_event_revisions_and_returns_latest(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        v1 = _event()
        v2 = CanonicalEvent(**{**v1.__dict__, "revision": 2, "status": EventStatus.SUPERSEDED})
        store.save_event(v1)
        store.save_event(v2)
        assert store.get_latest_event(v1.event_id) == v2
        assert store.list_event_revisions(v1.event_id) == (v1, v2)
    finally:
        store.close()


def test_identical_same_revision_write_is_idempotent_but_conflict_is_rejected(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        claim = _claim()
        store.save_claim(claim)
        store.save_claim(claim)
        with pytest.raises(KnowledgeStoreConflict):
            store.save_claim(_claim(statement="Different claim text"))
    finally:
        store.close()


def test_system_as_known_state_round_trips(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        state = KnowledgeState(
            state_id="Ksys:2026-08-31T10:00:00Z",
            mode=KnowledgeMode.SYSTEM_AS_KNOWN,
            as_of="2026-08-31T10:00:00Z",
            policy_version="ai-daily-policy-v1",
            claim_ids=("claim:model-x-release",),
            event_ids=("evt:model-x-release",),
            metadata={"batchable": True},
        )
        store.save_knowledge_state(state)
        assert store.get_knowledge_state(state.state_id) == state
    finally:
        store.close()
