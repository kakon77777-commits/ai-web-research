from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue


class PatentLegalValueClass(StrEnum):
    OFFICIAL_LEGAL_TEXT = "official_legal_text"
    OFFICIAL_DATA = "official_data"
    SEARCH_TEXT = "search_text"
    OCR_SEARCH_TEXT = "ocr_search_text"
    MACHINE_TRANSLATION = "machine_translation"
    SECONDARY_REPRESENTATION = "secondary_representation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PatentClaim:
    patent_claim_id: str
    publication_number: str
    claim_number: int
    text: str
    language: str | None
    legal_value_class: PatentLegalValueClass
    is_legally_authoritative: bool
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PatentFamilyFold:
    fold_id: str
    family_id: str | None
    publication_numbers: tuple[str, ...]
    candidate_refs: tuple[str, ...]
    representative_candidate_ref: str


class ChronologyClass(StrEnum):
    BEFORE_CUTOFF = "before_cutoff"
    ON_CUTOFF = "on_cutoff"
    AFTER_CUTOFF = "after_cutoff"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PatentPriorityChronology:
    candidate_ref: str
    earliest_priority_date: str | None
    publication_date: str | None
    cutoff: str | None
    priority_class: ChronologyClass
    publication_class: ChronologyClass


@dataclass(frozen=True)
class NPLCandidate:
    candidate_id: str
    persistent_id: str | None
    title: str | None
    publication_date: str | None
    publisher: str | None
    authors: tuple[str, ...]
    provider_ref: str
    source_type: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)
