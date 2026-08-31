from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
import sqlite3
from pathlib import Path

from .models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimOrigin,
    ClaimState,
    EventStatus,
    KnowledgeMode,
    KnowledgeState,
    ValidTime,
)


class KnowledgeStoreConflict(ValueError):
    pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_claim_revisions (
    claim_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (claim_id, revision)
);
CREATE TABLE IF NOT EXISTS canonical_event_revisions (
    event_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (event_id, revision)
);
CREATE TABLE IF NOT EXISTS knowledge_states (
    state_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);
"""


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if is_dataclass(value):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    raise TypeError(type(value).__name__)


def _dump(value) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _valid_time(data) -> ValidTime | None:
    if data is None:
        return None
    return ValidTime(start=data.get("start"), end=data.get("end"))


def _claim(data: dict) -> CanonicalClaim:
    return CanonicalClaim(
        claim_id=data["claim_id"],
        revision=int(data["revision"]),
        statement=data["statement"],
        subject_id=data.get("subject_id"),
        predicate=data.get("predicate"),
        object_value=data.get("object_value"),
        state=ClaimState(data["state"]),
        claim_origin=ClaimOrigin(data["claim_origin"]),
        evidence_ids=tuple(data.get("evidence_ids", ())),
        independent_root_count=int(data.get("independent_root_count", 0)),
        known_at=data["known_at"],
        valid_time=_valid_time(data.get("valid_time")),
        metadata=data.get("metadata", {}),
    )


def _event(data: dict) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=data["event_id"],
        revision=int(data["revision"]),
        event_type=data["event_type"],
        entity_ids=tuple(data.get("entity_ids", ())),
        status=EventStatus(data["status"]),
        claim_ids=tuple(data.get("claim_ids", ())),
        evidence_ids=tuple(data.get("evidence_ids", ())),
        known_at=data["known_at"],
        valid_time=_valid_time(data.get("valid_time")),
        metadata=data.get("metadata", {}),
    )


def _state(data: dict) -> KnowledgeState:
    return KnowledgeState(
        state_id=data["state_id"],
        mode=KnowledgeMode(data["mode"]),
        as_of=data["as_of"],
        policy_version=data["policy_version"],
        claim_ids=tuple(data.get("claim_ids", ())),
        event_ids=tuple(data.get("event_ids", ())),
        metadata=data.get("metadata", {}),
    )


class KnowledgeStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _save_revision(self, *, table: str, id_column: str, object_id: str, revision: int, payload: str) -> None:
        existing = self._conn.execute(
            f"SELECT payload_json FROM {table} WHERE {id_column}=? AND revision=?",
            (object_id, revision),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] == payload:
                return
            raise KnowledgeStoreConflict(f"conflicting {object_id}@{revision}")
        self._conn.execute(
            f"INSERT INTO {table} ({id_column}, revision, payload_json) VALUES (?, ?, ?)",
            (object_id, revision, payload),
        )
        self._conn.commit()

    def save_claim(self, claim: CanonicalClaim) -> None:
        self._save_revision(
            table="canonical_claim_revisions",
            id_column="claim_id",
            object_id=claim.claim_id,
            revision=claim.revision,
            payload=_dump(claim),
        )

    def get_latest_claim(self, claim_id: str) -> CanonicalClaim:
        row = self._conn.execute(
            "SELECT payload_json FROM canonical_claim_revisions WHERE claim_id=? ORDER BY revision DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise KeyError(claim_id)
        return _claim(json.loads(row["payload_json"]))

    def list_claim_revisions(self, claim_id: str) -> tuple[CanonicalClaim, ...]:
        rows = self._conn.execute(
            "SELECT payload_json FROM canonical_claim_revisions WHERE claim_id=? ORDER BY revision ASC",
            (claim_id,),
        ).fetchall()
        return tuple(_claim(json.loads(row["payload_json"])) for row in rows)

    def save_event(self, event: CanonicalEvent) -> None:
        self._save_revision(
            table="canonical_event_revisions",
            id_column="event_id",
            object_id=event.event_id,
            revision=event.revision,
            payload=_dump(event),
        )

    def get_latest_event(self, event_id: str) -> CanonicalEvent:
        row = self._conn.execute(
            "SELECT payload_json FROM canonical_event_revisions WHERE event_id=? ORDER BY revision DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        return _event(json.loads(row["payload_json"]))

    def list_event_revisions(self, event_id: str) -> tuple[CanonicalEvent, ...]:
        rows = self._conn.execute(
            "SELECT payload_json FROM canonical_event_revisions WHERE event_id=? ORDER BY revision ASC",
            (event_id,),
        ).fetchall()
        return tuple(_event(json.loads(row["payload_json"])) for row in rows)

    def save_knowledge_state(self, state: KnowledgeState) -> None:
        payload = _dump(state)
        row = self._conn.execute("SELECT payload_json FROM knowledge_states WHERE state_id=?", (state.state_id,)).fetchone()
        if row is not None:
            if row["payload_json"] == payload:
                return
            raise KnowledgeStoreConflict(f"conflicting knowledge state {state.state_id}")
        self._conn.execute(
            "INSERT INTO knowledge_states (state_id, payload_json) VALUES (?, ?)",
            (state.state_id, payload),
        )
        self._conn.commit()

    def get_knowledge_state(self, state_id: str) -> KnowledgeState:
        row = self._conn.execute("SELECT payload_json FROM knowledge_states WHERE state_id=?", (state_id,)).fetchone()
        if row is None:
            raise KeyError(state_id)
        return _state(json.loads(row["payload_json"]))
