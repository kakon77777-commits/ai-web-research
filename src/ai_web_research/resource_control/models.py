from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AnytimeStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True)
class ResearchBudget:
    max_selected_events: int
    max_watch_events: int = 0

    def __post_init__(self) -> None:
        if self.max_selected_events < 0:
            raise ValueError("max_selected_events must be >= 0")
        if self.max_watch_events < 0:
            raise ValueError("max_watch_events must be >= 0")
