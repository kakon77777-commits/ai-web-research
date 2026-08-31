from __future__ import annotations

from dataclasses import dataclass, replace

from ai_web_research.domains.patents.models import PatentCandidate, PatentFamilyIdentity
from ai_web_research.execution.models import ProviderObservation


@dataclass(frozen=True)
class PatentFamilyFoldResult:
    families: dict[str, tuple[PatentCandidate, ...]]
    unresolved: tuple[PatentCandidate, ...]


def family_from_observation(observation: ProviderObservation) -> PatentFamilyIdentity:
    for artifact in observation.artifacts:
        meta = artifact.metadata
        if meta.get("source_type") != "epo_ops_family":
            continue
        family_id = artifact.id.removeprefix("epo:family:")
        return PatentFamilyIdentity(
            family_id=family_id,
            family_type=str(meta.get("family_type") or "UNKNOWN"),
            provider=observation.provider_id,
            definition_version=str(meta.get("definition_version") or "OPS-3.2"),
            member_publications=tuple(str(x) for x in (meta.get("member_publications") or [])),
            priority_refs=tuple(str(x) for x in (meta.get("priority_refs") or [])),
            priority_dates=tuple(str(x) for x in (meta.get("priority_dates") or [])),
        )
    raise ValueError("observation does not contain an EPO family record")


def attach_family_identity(
    candidates: tuple[PatentCandidate, ...],
    family: PatentFamilyIdentity,
) -> tuple[PatentCandidate, ...]:
    members = set(family.member_publications)
    return tuple(
        replace(candidate, family_id=family.family_id)
        if candidate.publication_number in members
        else candidate
        for candidate in candidates
    )


def fold_candidates_by_family(
    candidates: tuple[PatentCandidate, ...],
) -> PatentFamilyFoldResult:
    families: dict[str, list[PatentCandidate]] = {}
    unresolved: list[PatentCandidate] = []
    for candidate in candidates:
        if candidate.family_id:
            families.setdefault(candidate.family_id, []).append(candidate)
        else:
            unresolved.append(candidate)
    return PatentFamilyFoldResult(
        families={key: tuple(value) for key, value in sorted(families.items())},
        unresolved=tuple(unresolved),
    )
