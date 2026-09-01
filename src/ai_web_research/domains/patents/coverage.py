from __future__ import annotations

from dataclasses import dataclass

from .models import PatentCoverageState, PatentGapType


@dataclass(frozen=True)
class PatentBranchRecord:
    branch_id: str
    branch_type: str
    method_id: str
    provider_id: str
    status: str
    features: tuple[str, ...]
    classifications: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    languages: tuple[str, ...]
    result_count: int


@dataclass(frozen=True)
class PatentCoverageEvaluation:
    coverage: PatentCoverageState
    gaps: tuple[PatentGapType, ...]
    branch_refs: tuple[str, ...]


def _coverage(required, searched):
    return {item: ("searched" if item in searched else "unsearched") for item in required}


def evaluate_patent_coverage(
    *,
    required_features,
    required_classifications,
    required_jurisdictions,
    required_languages,
    include_npl,
    include_backward_citation,
    authoritative_claim_manifestations_verified,
    branches,
):
    searched = [branch for branch in branches if branch.status == "searched"]
    searched_features = {x for branch in searched for x in branch.features}
    searched_classes = {x for branch in searched for x in branch.classifications}
    searched_jurisdictions = {x for branch in searched for x in branch.jurisdictions}
    searched_languages = {x for branch in searched for x in branch.languages}
    npl_searched = any(branch.branch_type == "NPL_BRANCH" for branch in searched)
    backward_searched = any(branch.branch_type == "CITATION_BACKWARD_BRANCH" for branch in searched)

    coverage = PatentCoverageState(
        feature_coverage=_coverage(required_features, searched_features),
        classification_coverage=_coverage(required_classifications, searched_classes),
        jurisdiction_coverage=_coverage(required_jurisdictions, searched_jurisdictions),
        language_coverage=_coverage(required_languages, searched_languages),
        chronology_coverage={},
        citation_coverage={"backward": "searched" if backward_searched else "unsearched"},
        npl_coverage={"required": "searched" if npl_searched else "unsearched"},
        provider_coverage={branch.provider_id: "searched" for branch in searched},
        method_coverage={branch.method_id: "searched" for branch in searched},
    )

    gaps = set()
    if "unsearched" in coverage.feature_coverage.values():
        gaps.add(PatentGapType.FEATURE_UNSEARCHED)
    if "unsearched" in coverage.classification_coverage.values():
        gaps.add(PatentGapType.CLASSIFICATION_UNSEARCHED)
    if "unsearched" in coverage.jurisdiction_coverage.values():
        gaps.add(PatentGapType.JURISDICTION_UNSEARCHED)
    if "unsearched" in coverage.language_coverage.values():
        gaps.add(PatentGapType.LANGUAGE_UNSEARCHED)
    if include_npl and not npl_searched:
        gaps.add(PatentGapType.NPL_UNSEARCHED)
    if include_backward_citation and not backward_searched:
        gaps.add(PatentGapType.CITATION_BACKWARD_UNSEARCHED)
    if not authoritative_claim_manifestations_verified:
        gaps.add(PatentGapType.LEGAL_MANIFESTATION_NOT_VERIFIED)

    return PatentCoverageEvaluation(
        coverage=coverage,
        gaps=tuple(sorted(gaps, key=lambda gap: gap.value)),
        branch_refs=tuple(branch.branch_id for branch in branches),
    )
