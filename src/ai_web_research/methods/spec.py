from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import ArtifactKind, JsonValue


class MethodGoal(StrEnum):
    LOCATE = "locate"
    NARROW = "narrow"
    EXPAND = "expand"
    DISCOVER = "discover"
    RELATE = "relate"
    VERIFY = "verify"
    FALSIFY = "falsify"
    RECONCILE = "reconcile"
    MONITOR = "monitor"


class RepresentationKind(StrEnum):
    IDENTIFIER = "identifier"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    STRUCTURED = "structured"
    TAXONOMY = "taxonomy"
    GRAPH = "graph"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    MULTIMODAL = "multimodal"


class SearchDirection(StrEnum):
    INWARD = "inward"
    OUTWARD = "outward"
    FORWARD = "forward"
    BACKWARD = "backward"
    LATERAL = "lateral"
    CROSS_SOURCE = "cross_source"
    CROSS_LANGUAGE = "cross_language"
    CROSS_MODAL = "cross_modal"


class InteractionMode(StrEnum):
    ONE_SHOT = "one_shot"
    FEEDBACK = "feedback"
    ITERATIVE = "iterative"
    ADAPTIVE = "adaptive"
    CONTINUOUS = "continuous"


class EvidenceEffect(StrEnum):
    CANDIDATE = "candidate"
    METADATA = "metadata"
    PRIMARY_SOURCE = "primary_source"
    SECONDARY_SOURCE = "secondary_source"
    RELATION = "relation"
    CORROBORATION = "corroboration"
    CONTRADICTION = "contradiction"
    QUALIFICATION = "qualification"
    VERSION = "version"
    NONE = "none"


class MethodAvailability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class FailureSpec:
    code: str
    description: str
    recoverable: bool
    suggested_gap_type: str | None = None


@dataclass(frozen=True)
class ContractSpec:
    accepts: frozenset[ArtifactKind] = field(default_factory=frozenset)
    produces: frozenset[ArtifactKind] = field(default_factory=frozenset)
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchMethodSpec:
    method_id: str
    version: str
    availability: MethodAvailability
    aliases: tuple[str, ...]
    purpose: str
    goals: frozenset[MethodGoal]
    representations: frozenset[RepresentationKind]
    directions: frozenset[SearchDirection]
    interaction_modes: frozenset[InteractionMode]
    evidence_effects: frozenset[EvidenceEffect]
    input_contract: ContractSpec
    output_contract: ContractSpec
    parameter_schema: dict[str, JsonValue]
    required_capabilities: frozenset[str]
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    failure_modes: tuple[FailureSpec, ...]
    cost_prior: dict[str, JsonValue]
    latency_prior: dict[str, JsonValue]
    receipt_requirements: tuple[str, ...]
    stopping_implications: tuple[str, ...]
    metadata: dict[str, JsonValue]
