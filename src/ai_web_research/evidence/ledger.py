from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import JsonValue


@dataclass(frozen=True)
class EvidenceLedgerEvent:
    sequence: int
    event_id: str
    event_type: str
    subject_type: str
    subject_id: str
    actor_id: str
    actor_version: str | None
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    payload: dict[str, JsonValue]
    created_at: str


class EvidenceLedger:
    def __init__(self, store) -> None:
        self._store = store

    def append(
        self,
        *,
        event_id: str,
        event_type: str,
        subject_type: str,
        subject_id: str,
        actor_id: str,
        actor_version: str | None,
        input_refs: tuple[str, ...],
        output_refs: tuple[str, ...],
        payload: dict[str, JsonValue],
        created_at: str,
    ) -> EvidenceLedgerEvent:
        return self._store.append_ledger_event(
            event_id=event_id,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            actor_id=actor_id,
            actor_version=actor_version,
            input_refs=input_refs,
            output_refs=output_refs,
            payload=payload,
            created_at=created_at,
        )

    def list_events(self) -> tuple[EvidenceLedgerEvent, ...]:
        return self._store.list_ledger_events()
