from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ai_web_research.domains.patents.models import PatentCandidate


class CutoffRelation(StrEnum):
    BEFORE_OR_ON = "before_or_on"
    AFTER = "after"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PatentChronologyEntry:
    candidate_id: str
    publication_number: str | None
    earliest_priority: str | None
    publication_date: str | None
    cutoff_relation: CutoffRelation
    priority_resolved: bool


def build_priority_chronology(
    candidates: tuple[PatentCandidate, ...],
    *,
    cutoff: str | None,
) -> tuple[PatentChronologyEntry, ...]:
    result: list[PatentChronologyEntry] = []
    for candidate in candidates:
        priorities = tuple(sorted(p for p in candidate.priority_dates if p))
        earliest = priorities[0] if priorities else None
        if earliest is None or cutoff is None:
            relation = CutoffRelation.UNKNOWN
        elif earliest <= cutoff:
            relation = CutoffRelation.BEFORE_OR_ON
        else:
            relation = CutoffRelation.AFTER
        result.append(
            PatentChronologyEntry(
                candidate.candidate_id,
                candidate.publication_number,
                earliest,
                candidate.publication_date,
                relation,
                earliest is not None,
            )
        )
    return tuple(result)
