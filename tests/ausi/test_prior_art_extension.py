from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.domains.patents.coverage import PatentBranchRecord, evaluate_patent_coverage
from ai_web_research.domains.patents.prior_art_materialize import chronology, patent_candidate, patent_claims


def test_typed_candidate_chronology_and_claim_legal_boundary():
    artifact = ArtifactRef(
        ArtifactKind.CANDIDATE,
        "epo:publication:EP1A1",
        metadata={
            "publication_number": "EP1A1",
            "application_number": "EP1A",
            "priority_dates": ["2024-01-01"],
            "publication_date": "2026-01-01",
            "cpc": ["G06F16/00"],
            "ipc": [],
            "source_type": "epo_ops_bibliographic",
            "score_semantics": "epo_ops_provider_order",
            "docdb_publication": "EP.1.A1",
            "epodoc_publication": "EP1",
        },
    )
    candidate = patent_candidate(artifact)
    timeline = chronology(candidate, "2025-01-01")
    assert timeline.priority_class.value == "before_cutoff"
    assert timeline.publication_class.value == "after_cutoff"

    claims_artifact = ArtifactRef(
        ArtifactKind.DOCUMENT,
        "epo:claims:EP1A1",
        metadata={
            "publication_number": "EP1A1",
            "claims": [{"claim_number": 1, "text": "1. A system."}],
            "legal_value_class": "official_data",
            "manifestation_verification_required": True,
        },
    )
    claim = patent_claims(claims_artifact)[0]
    assert claim.publication_number == "EP1A1"
    assert claim.is_legally_authoritative is False


def test_coverage_requires_npl_citation_scope_and_legal_manifestation_when_declared():
    branches = (
        PatentBranchRecord(
            branch_id="lexical",
            branch_type="FEATURE_BRANCH",
            method_id="method.lexical_search",
            provider_id="provider.epo_ops",
            status="searched",
            features=("feature.1",),
            classifications=(),
            jurisdictions=("EP",),
            languages=("en",),
            result_count=3,
        ),
        PatentBranchRecord(
            branch_id="class",
            branch_type="CLASSIFICATION_BRANCH",
            method_id="method.patent.classification_search",
            provider_id="provider.epo_ops",
            status="searched",
            features=("feature.1",),
            classifications=("G06F16/00",),
            jurisdictions=("EP",),
            languages=("en",),
            result_count=4,
        ),
    )
    result = evaluate_patent_coverage(
        required_features=("feature.1",),
        required_classifications=("G06F16/00",),
        required_jurisdictions=("EP", "US"),
        required_languages=("en",),
        include_npl=True,
        include_backward_citation=True,
        authoritative_claim_manifestations_verified=False,
        branches=branches,
    )
    gaps = {gap.value for gap in result.gaps}
    assert gaps == {
        "jurisdiction_unsearched",
        "npl_unsearched",
        "citation_backward_unsearched",
        "legal_manifestation_not_verified",
    }
    assert result.coverage.feature_coverage["feature.1"] == "searched"
