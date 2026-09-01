
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue


class PatentIdentifierType(StrEnum):
    PUBLICATION = "publication"
    APPLICATION = "application"
    GRANT = "grant"
    PCT = "pct"
    PRIORITY = "priority"
    FAMILY = "family"
    OTHER = "other"


class ClassificationScheme(StrEnum):
    IPC = "ipc"
    CPC = "cpc"
    NATIONAL = "national"
    LEGACY = "legacy"


class PatentGapType(StrEnum):
    FEATURE_UNSEARCHED = "feature_unsearched"
    FEATURE_COMBINATION_UNSEARCHED = "feature_combination_unsearched"
    CLASSIFICATION_UNSEARCHED = "classification_unsearched"
    CLASSIFICATION_VERSION_UNKNOWN = "classification_version_unknown"
    LANGUAGE_UNSEARCHED = "language_unsearched"
    JURISDICTION_UNSEARCHED = "jurisdiction_unsearched"
    PRIORITY_UNRESOLVED = "priority_unresolved"
    PUBLICATION_CUTOFF_UNRESOLVED = "publication_cutoff_unresolved"
    FAMILY_UNRESOLVED = "family_unresolved"
    CLAIM_VERSION_UNRESOLVED = "claim_version_unresolved"
    CITATION_BACKWARD_UNSEARCHED = "citation_backward_unsearched"
    CITATION_FORWARD_UNSEARCHED = "citation_forward_unsearched"
    NPL_UNSEARCHED = "npl_unsearched"
    LEGAL_STATUS_UNRESOLVED = "legal_status_unresolved"
    LEGAL_MANIFESTATION_NOT_VERIFIED = "legal_manifestation_not_verified"
    COUNTER_PATH_UNSEARCHED = "counter_path_unsearched"
    PROVIDER_POLICY_BLOCKED = "provider_policy_blocked"


@dataclass(frozen=True)
class PatentIdentifier:
    identifier_type: PatentIdentifierType
    authority: str | None
    value: str
    normalized_value: str


@dataclass(frozen=True)
class ClassificationIdentity:
    scheme: ClassificationScheme
    symbol: str
    version: str
    title: str | None
    definition_ref: str | None
    parent_symbols: tuple[str, ...]
    effective_at: str | None


@dataclass(frozen=True)
class InventionFeature:
    feature_id: str
    description: str
    function: str | None
    mechanism: str | None
    input_state: str | None
    output_state: str | None
    constraints: tuple[str, ...]
    dependencies: tuple[str, ...]
    importance: float | None
    novelty_hypothesis: str | None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PatentConcept:
    concept_id: str
    feature_refs: tuple[str, ...]
    functional_terms: tuple[str, ...]
    structural_terms: tuple[str, ...]
    mechanism_terms: tuple[str, ...]
    patent_style_terms: tuple[str, ...]
    historical_terms: tuple[str, ...]
    synonyms: tuple[str, ...]
    broader_terms: tuple[str, ...]
    narrower_terms: tuple[str, ...]
    translations: dict[str, tuple[str, ...]]
    classification_hints: tuple[str, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PriorityClaim:
    priority_id: str
    application_number: str
    jurisdiction: str | None
    filing_date: str
    relationship: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class PatentFamilyIdentity:
    family_id: str
    family_type: str
    provider: str
    definition_version: str | None
    member_publications: tuple[str, ...]
    priority_refs: tuple[str, ...]
    priority_dates: tuple[str, ...] = ()


@dataclass(frozen=True)
class PatentCandidate:
    candidate_id: str
    publication_number: str | None
    application_number: str | None
    family_id: str | None
    title: str | None
    abstract: str | None
    classifications: tuple[str, ...]
    priority_dates: tuple[str, ...]
    publication_date: str | None
    applicant_refs: tuple[str, ...]
    inventor_refs: tuple[str, ...]
    retrieval_score: float | None
    score_semantics: str
    provider_refs: tuple[str, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PatentCoverageState:
    feature_coverage: dict[str, JsonValue]
    classification_coverage: dict[str, JsonValue]
    jurisdiction_coverage: dict[str, JsonValue]
    language_coverage: dict[str, JsonValue]
    chronology_coverage: dict[str, JsonValue]
    citation_coverage: dict[str, JsonValue]
    npl_coverage: dict[str, JsonValue]
    provider_coverage: dict[str, JsonValue]
    method_coverage: dict[str, JsonValue]


@dataclass(frozen=True)
class PatentSearchTaskExtension:
    task_type: str
    target_invention_ref: str | None
    target_product_ref: str | None
    target_jurisdictions: tuple[str, ...]
    target_languages: tuple[str, ...]
    filing_or_priority_cutoff: str | None
    publication_cutoff: str | None
    required_classifications: tuple[str, ...]
    include_npl: bool
    include_citations: bool
    include_legal_status: bool
    recall_target: str
    verification_profile: str
    human_review_required: bool
    metadata: dict[str, JsonValue] = field(default_factory=dict)
