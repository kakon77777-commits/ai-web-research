from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue


class AnchorKind(StrEnum):
    TEXT_SPAN = "text_span"
    PAGE_PARAGRAPH = "page_paragraph"
    JSON_PATH = "json_path"
    TABLE_CELL = "table_cell"
    TIME_SERIES_OBSERVATION = "time_series_observation"
    PATENT_CLAIM = "patent_claim"
    CODE_SPAN = "code_span"
    IMAGE_REGION = "image_region"
    AUDIO_SEGMENT = "audio_segment"
    GENERIC = "generic"


@dataclass(frozen=True)
class EvidenceAnchor:
    anchor_id: str
    kind: AnchorKind
    manifestation_id: str | None
    locator: dict[str, JsonValue]
    anchored_text: str | None
    anchored_hash: str | None
    created_at: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)
