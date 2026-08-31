from __future__ import annotations

from dataclasses import dataclass, field

from ai_web_research.core.types import JsonValue


@dataclass(frozen=True)
class ProjectionUnit:
    unit_id: str
    text: str
    claim_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    status_label: str


@dataclass(frozen=True)
class ProjectionArtifact:
    artifact_id: str
    channel: str
    knowledge_state_id: str
    revision: int
    units: tuple[ProjectionUnit, ...]
    generated_at: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("revision must be >= 1")


@dataclass(frozen=True)
class CorrectionImpact:
    claim_id: str
    artifact_ids: tuple[str, ...]
