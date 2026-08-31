from __future__ import annotations

from ai_web_research.execution.models import ProviderObservation
from ai_web_research.domains.patents.models import PatentCandidate


def patent_candidates_from_observation(observation: ProviderObservation) -> tuple[PatentCandidate, ...]:
    result: list[PatentCandidate] = []
    for artifact in observation.artifacts:
        metadata = artifact.metadata
        if metadata.get("source_type") != "epo_ops_bibliographic":
            continue
        publication_number = metadata.get("publication_number")
        if not publication_number:
            continue
        classifications = tuple(
            str(x)
            for x in (
                list(metadata.get("cpc") or [])
                + list(metadata.get("ipc") or [])
            )
        )
        result.append(
            PatentCandidate(
                candidate_id=artifact.id,
                publication_number=str(publication_number),
                application_number=(
                    str(metadata["application_number"])
                    if metadata.get("application_number") else None
                ),
                family_id=(
                    str(metadata["family_id"]) if metadata.get("family_id") else None
                ),
                title=str(metadata["title"]) if metadata.get("title") else None,
                abstract=str(metadata["abstract"]) if metadata.get("abstract") else None,
                classifications=classifications,
                priority_dates=tuple(str(x) for x in (metadata.get("priority_dates") or [])),
                publication_date=(
                    str(metadata["publication_date"])
                    if metadata.get("publication_date") else None
                ),
                applicant_refs=tuple(str(x) for x in (metadata.get("applicants") or [])),
                inventor_refs=tuple(str(x) for x in (metadata.get("inventors") or [])),
                retrieval_score=None,
                score_semantics=str(metadata.get("score_semantics") or "unknown"),
                provider_refs=(observation.provider_id,),
                metadata=dict(metadata),
            )
        )
    return tuple(result)
