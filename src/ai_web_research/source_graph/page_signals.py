from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PageSourceSignalKind(StrEnum):
    CANONICAL_URL = "canonical_url"
    SYNDICATION_SOURCE = "syndication_source"
    ORIGINAL_SOURCE = "original_source"
    BASED_ON = "based_on"
    CITATION_URL = "citation_url"
    ATTRIBUTED_URL = "attributed_url"
    ATTRIBUTION_ENTITY = "attribution_entity"
    QUOTED_PHRASE = "quoted_phrase"
    OWNER_HINT = "owner_hint"


@dataclass(frozen=True)
class PageSourceSignal:
    signal_id: str
    source_id: str
    kind: PageSourceSignalKind
    value: str
    locator: str
    confidence: float
    explicit: bool


@dataclass(frozen=True)
class PageSignalExtraction:
    source_id: str
    signals: tuple[PageSourceSignal, ...]
    warnings: tuple[str, ...]
    truncated: bool
    parser_version: str
