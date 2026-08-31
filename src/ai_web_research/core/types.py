from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class VersionRef:
    id: str
    version: str


class ArtifactKind(StrEnum):
    TASK = "task"
    QUERY = "query"
    QUERY_SET = "query_set"
    IDENTIFIER = "identifier"
    SEED = "seed"
    CANDIDATE = "candidate"
    CANDIDATE_SET = "candidate_set"
    DOCUMENT_REF = "document_ref"
    DOCUMENT = "document"
    STRUCTURED_RECORD = "structured_record"
    EVIDENCE_CANDIDATE = "evidence_candidate"
    VERIFIED_EVIDENCE = "verified_evidence"
    CLAIM = "claim"
    GAP = "gap"
    COVERAGE_STATE = "coverage_state"
    SYNTHESIS = "synthesis"
    POLICY_REF = "policy_ref"


@dataclass(frozen=True)
class ArtifactRef:
    kind: ArtifactKind
    id: str
    version: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


class SearchIntent(StrEnum):
    LOCATE = "locate"
    DISCOVER = "discover"
    VERIFY = "verify"
    FALSIFY = "falsify"
    COMPARE = "compare"
    MONITOR = "monitor"
    RESEARCH = "research"
    RESOLVE_IDENTITY = "resolve_identity"
    RESOLVE_VERSION = "resolve_version"


class RiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROFESSIONAL_REVIEW = "professional_review"


@dataclass(frozen=True)
class SearchTask:
    task_id: str
    raw_request: str
    intent: SearchIntent
    domain: str | None
    purpose: str | None
    languages: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    freshness: dict[str, JsonValue]
    coverage_requirements: dict[str, JsonValue]
    verification_requirements: dict[str, JsonValue]
    source_preferences: tuple[str, ...]
    risk_class: RiskClass
    budget: dict[str, JsonValue]
    domain_pack: str | None
    metadata: dict[str, JsonValue]


class ActionKind(StrEnum):
    SEARCH = "search"
    FETCH = "fetch"
    CRAWL = "crawl"
    QUERY_TRANSFORM = "query_transform"
    RESOLVE_IDENTITY = "resolve_identity"
    EXTRACT = "extract"
    VERIFY = "verify"
    SYNTHESIZE = "synthesize"
    STOP = "stop"


@dataclass(frozen=True)
class SearchAction:
    action_id: str
    task_id: str
    epoch_id: str
    method_ref: VersionRef
    provider_ref: VersionRef
    surface_id: str
    binding_id: str
    action_kind: ActionKind
    inputs: tuple[ArtifactRef, ...]
    parameters: dict[str, JsonValue]
    guards: tuple[str, ...]
    expected_effects: tuple[str, ...]
    created_by: str
    created_at: str


@dataclass(frozen=True)
class StopAction:
    action_id: str
    task_id: str
    epoch_id: str
    reason: str
    state_ref: str
    created_by: str
    created_at: str


@dataclass
class SearchState:
    task_id: str
    epoch_id: str
    planned_at: str
    active_artifacts: list[ArtifactRef]
    candidate_refs: list[str]
    evidence_refs: list[str]
    open_gap_refs: list[str]
    completed_action_ids: list[str]
    failed_action_ids: list[str]
    budget_state: dict[str, JsonValue]
    coverage_state: dict[str, JsonValue]
    metadata: dict[str, JsonValue]
