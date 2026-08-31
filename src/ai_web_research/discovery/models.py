from __future__ import annotations
from dataclasses import dataclass, field
from ai_web_research.core.types import JsonValue

@dataclass(frozen=True)
class DiscoveryCandidate:
    candidate_id: str
    url: str
    title: str | None
    snippet: str | None
    provider_id: str
    surface_id: str
    provider_rank: int
    artifact_ids: tuple[str, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)

@dataclass(frozen=True)
class DiscoveryBatch:
    observation_id: str
    query: str
    candidates: tuple[DiscoveryCandidate, ...]
    provider_id: str
    occurred_at: str
