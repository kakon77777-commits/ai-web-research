from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.domains.patents.family import PatentFamilyFoldResult
from ai_web_research.domains.patents.models import (
    PatentCandidate,
    PatentCoverageState,
    PatentGapType,
    PatentSearchTaskExtension,
)


@dataclass(frozen=True)
class PatentIdentityCoverageAnalysis:
    coverage: PatentCoverageState
    gaps: tuple[PatentGapType, ...]


def _axis(required: tuple[str, ...], searched: tuple[str, ...]) -> dict[str, str]:
    searched_set = set(searched)
    return {item: ("searched" if item in searched_set else "unsearched") for item in required}


def analyze_identity_coverage(
    task: PatentSearchTaskExtension,
    *,
    candidates: tuple[PatentCandidate, ...],
    family_fold: PatentFamilyFoldResult,
    required_feature_ids: tuple[str, ...],
    searched_feature_ids: tuple[str, ...],
    searched_classifications: tuple[str, ...],
    searched_jurisdictions: tuple[str, ...],
    searched_languages: tuple[str, ...],
    searched_methods: tuple[str, ...],
    searched_providers: tuple[str, ...],
    npl_searched: bool,
    backward_citations_searched: bool,
    forward_citations_searched: bool,
    counter_path_searched: bool,
) -> PatentIdentityCoverageAnalysis:
    feature = _axis(required_feature_ids, searched_feature_ids)
    classification = _axis(task.required_classifications, searched_classifications)
    jurisdiction = _axis(task.target_jurisdictions, searched_jurisdictions)
    language = _axis(task.target_languages, searched_languages)
    chronology = {
        "priority": "searched" if all(c.priority_dates for c in candidates) else "partial",
        "publication_cutoff": "searched" if task.publication_cutoff else "unresolved",
    }
    citation = {
        "backward": "searched" if backward_citations_searched else "unsearched",
        "forward": "searched" if forward_citations_searched else "unsearched",
    }
    npl = {"npl": "searched" if npl_searched else "unsearched"}
    provider = {provider: "searched" for provider in searched_providers}
    method = {method_id: "searched" for method_id in searched_methods}
    coverage = PatentCoverageState(
        feature_coverage=feature,
        classification_coverage=classification,
        jurisdiction_coverage=jurisdiction,
        language_coverage=language,
        chronology_coverage=chronology,
        citation_coverage=citation,
        npl_coverage=npl,
        provider_coverage=provider,
        method_coverage=method,
    )

    gaps: set[PatentGapType] = set()
    if any(value == "unsearched" for value in feature.values()):
        gaps.add(PatentGapType.FEATURE_UNSEARCHED)
    if any(value == "unsearched" for value in classification.values()):
        gaps.add(PatentGapType.CLASSIFICATION_UNSEARCHED)
    if any(value == "unsearched" for value in jurisdiction.values()):
        gaps.add(PatentGapType.JURISDICTION_UNSEARCHED)
    if any(value == "unsearched" for value in language.values()):
        gaps.add(PatentGapType.LANGUAGE_UNSEARCHED)
    if family_fold.unresolved:
        gaps.add(PatentGapType.FAMILY_UNRESOLVED)
    if any(not candidate.priority_dates for candidate in candidates):
        gaps.add(PatentGapType.PRIORITY_UNRESOLVED)
    if task.include_npl and not npl_searched:
        gaps.add(PatentGapType.NPL_UNSEARCHED)
    if task.include_citations and not backward_citations_searched:
        gaps.add(PatentGapType.CITATION_BACKWARD_UNSEARCHED)
    if task.include_citations and not forward_citations_searched:
        gaps.add(PatentGapType.CITATION_FORWARD_UNSEARCHED)
    if task.recall_target == "high" and not counter_path_searched:
        gaps.add(PatentGapType.COUNTER_PATH_UNSEARCHED)

    return PatentIdentityCoverageAnalysis(
        coverage=coverage,
        gaps=tuple(sorted(gaps, key=lambda gap: gap.value)),
    )
