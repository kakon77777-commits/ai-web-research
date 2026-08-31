from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from ai_web_research.core.types import JsonValue

class SourceRelationType(StrEnum):
    CITES='cites'
    LINKS_TO='links_to'
    MENTIONS='mentions'
    SYNDICATED_FROM='syndicated_from'
    MIRRORS='mirrors'
    DERIVED_FROM='derived_from'
    TRANSLATED_FROM='translated_from'
    SAME_ORIGIN_FAMILY='same_origin_family'

class RelationInferenceType(StrEnum):
    EXPLICIT='explicit'
    INFERRED='inferred'

@dataclass(frozen=True)
class SourceNode:
    source_id: str
    url: str
    canonical_url: str | None
    published_at: str | None
    observed_at: str
    owner_hint: str | None
    content_hash: str | None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

@dataclass(frozen=True)
class SourceRelation:
    relation_id: str
    from_source_id: str
    to_source_id: str
    relation_type: SourceRelationType
    confidence: float
    inference_type: RelationInferenceType
    signals: tuple[str, ...] = ()

@dataclass(frozen=True)
class SourceFamily:
    family_id: str
    member_source_ids: tuple[str, ...]
    root_source_id: str
    root_resolved: bool
    cycle_detected: bool

@dataclass(frozen=True)
class SourceFamilyResolution:
    source_to_family: dict[str, str]
    families: dict[str, SourceFamily]

    def independent_root_count(self, source_ids: tuple[str, ...]) -> int:
        roots: set[str] = set()
        for source_id in source_ids:
            family_id = self.source_to_family.get(source_id)
            roots.add(family_id if family_id is not None else f'unresolved:{source_id}')
        return len(roots)
