from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue


class ClaimState(StrEnum):
    OBSERVED = "observed"
    UNVERIFIED = "unverified"
    PARTIALLY_SUPPORTED = "partially_supported"
    WELL_SUPPORTED = "well_supported"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    RETRACTED = "retracted"


class ClaimOrigin(StrEnum):
    SOURCE_ASSERTION = "source_assertion"
    DERIVED_INFERENCE = "derived_inference"


class EventStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    CORRECTED = "corrected"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    RETRACTED = "retracted"
    MERGED = "merged"
    SPLIT = "split"


class KnowledgeMode(StrEnum):
    SYSTEM_AS_KNOWN = "SYSTEM_AS_KNOWN"
    PUBLIC_AS_AVAILABLE = "PUBLIC_AS_AVAILABLE"
    LATEST_VIEW_OF_PAST = "LATEST_VIEW_OF_PAST"


@dataclass(frozen=True)
class ValidTime:
    start: str | None
    end: str | None = None


@dataclass(frozen=True)
class CanonicalClaim:
    claim_id: str
    revision: int
    statement: str
    subject_id: str | None
    predicate: str | None
    object_value: JsonValue
    state: ClaimState
    claim_origin: ClaimOrigin
    evidence_ids: tuple[str, ...]
    independent_root_count: int
    known_at: str
    valid_time: ValidTime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("revision must be >= 1")
        if self.independent_root_count < 0:
            raise ValueError("independent_root_count must be >= 0")


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    revision: int
    event_type: str
    entity_ids: tuple[str, ...]
    status: EventStatus
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    known_at: str
    valid_time: ValidTime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("revision must be >= 1")


@dataclass(frozen=True)
class KnowledgeState:
    state_id: str
    mode: KnowledgeMode
    as_of: str
    policy_version: str
    claim_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)
