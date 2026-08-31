from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue
from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.knowledge.models import (
    ClaimOrigin,
    ClaimState,
    EventStatus,
    ValidTime,
)


class AIEntityType(StrEnum):
    ORGANIZATION = "organization"
    RESEARCH_LAB = "research_lab"
    RESEARCHER = "researcher"
    MODEL_FAMILY = "model_family"
    MODEL_VERSION = "model_version"
    PRODUCT = "product"
    API = "api"
    REPOSITORY = "repository"
    PAPER = "paper"
    BENCHMARK = "benchmark"
    LICENSE = "license"
    COMPUTE_PLATFORM = "compute_platform"
    CHIP = "chip"
    SUPPLIER = "supplier"
    INVESTOR = "investor"


class AIEventType(StrEnum):
    MODEL_RELEASE = "model_release"
    MODEL_UPDATE = "model_update"
    API_LAUNCH = "api_launch"
    OPEN_SOURCE_RELEASE = "open_source_release"
    PAPER_RELEASE = "paper_release"
    BENCHMARK_RESULT = "benchmark_result"
    FUNDING = "funding"
    RESEARCHER_MOVE = "researcher_move"
    CHIP_SUPPLY_CHANGE = "chip_supply_change"
    RUMOR_DETECTED = "rumor_detected"


@dataclass(frozen=True)
class AIIndustryEntity:
    entity_id: str
    entity_type: AIEntityType
    canonical_name: str
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, JsonValue] = field(default_factory=dict)
    status: str = "active"


@dataclass(frozen=True)
class ClaimDraft:
    claim_id: str
    statement: str
    subject_id: str | None
    predicate: str | None
    object_value: JsonValue
    state: ClaimState
    claim_origin: ClaimOrigin
    evidence: tuple[CandidateEvidence, ...]
    independent_root_count: int
    known_at: str
    valid_time: ValidTime | None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class EventDraft:
    event_id: str
    event_type: AIEventType
    entity_ids: tuple[str, ...]
    status: EventStatus
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    known_at: str
    valid_time: ValidTime | None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
