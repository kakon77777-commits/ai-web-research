from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.domains.patents.chronology import CutoffRelation, build_priority_chronology
from ai_web_research.domains.patents.family import (
    PatentFamilyFoldResult,
    attach_family_identity,
    family_from_observation,
    fold_candidates_by_family,
)
from ai_web_research.domains.patents.gap_analysis import analyze_identity_coverage
from ai_web_research.domains.patents.materialize import patent_candidates_from_observation
from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.domains.patents.models import PatentCandidate, PatentGapType, PatentSearchTaskExtension
from ai_web_research.domains.patents.prior_art_methods import register_prior_art_methods
from ai_web_research.execution.models import ObservationStatus, ProviderObservation
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry


def _candidate(publication: str, priorities=(), family_id=None):
    return PatentCandidate(
        candidate_id=f"cand:{publication}",
        publication_number=publication,
        application_number=None,
        family_id=family_id,
        title=publication,
        abstract=None,
        classifications=(),
        priority_dates=tuple(priorities),
        publication_date="2025-01-01",
        applicant_refs=(),
        inventor_refs=(),
        retrieval_score=None,
        score_semantics="test",
        provider_refs=("provider.epo_ops",),
        metadata={},
    )


def _task():
    return PatentSearchTaskExtension(
        task_type="PRIOR_ART_SEARCH",
        target_invention_ref="inv1",
        target_product_ref=None,
        target_jurisdictions=("EP", "JP"),
        target_languages=("en", "ja"),
        filing_or_priority_cutoff="2024-06-01",
        publication_cutoff="2024-06-01",
        required_classifications=("G06F16/00", "G06F40/30"),
        include_npl=True,
        include_citations=True,
        include_legal_status=False,
        recall_target="high",
        verification_profile="prior_art_high",
        human_review_required=True,
        metadata={},
    )


def test_patent_and_prior_art_method_registries_have_single_family_owner():
    registry = SearchMethodRegistry()
    register_builtin_methods(registry)
    register_patent_methods(registry)
    register_prior_art_methods(registry)
    assert registry.latest("method.patent.classification_search").metadata["domain"] == "patent_intelligence"
    assert registry.latest("method.patent.family_resolve").method_id == "method.patent.family_resolve"
    assert registry.latest("method.patent.claims_fetch").method_id == "method.patent.claims_fetch"


def test_epo_observation_materializes_typed_patent_candidate_only():
    observation = ProviderObservation(
        observation_id="obs1",
        action_id="a1",
        provider_id="provider.epo_ops",
        surface_id="surface.epo_ops.rest",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(
                ArtifactKind.CANDIDATE,
                "epo:publication:EP1234567A1",
                metadata={
                    "publication_number": "EP1234567A1",
                    "application_number": "EP25123456A",
                    "title": "Autonomous patent search",
                    "publication_date": "2026-01-15",
                    "priority_dates": ["2024-01-10"],
                    "applicants": ["Example Corp"],
                    "inventors": ["Ada Inventor"],
                    "cpc": ["G06F16/24578"],
                    "ipc": ["G06F16/245"],
                    "source_type": "epo_ops_bibliographic",
                    "score_semantics": "epo_ops_provider_order",
                },
            ),
            ArtifactRef(ArtifactKind.CANDIDATE, "crossref:x", metadata={"doi": "10/x"}),
        ),
        raw_ref=None,
        result_count=2,
        cost={},
        latency_ms=None,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T12:00:00+00:00",
        metadata={},
    )
    candidates = patent_candidates_from_observation(observation)
    assert len(candidates) == 1
    assert candidates[0].publication_number == "EP1234567A1"
    assert candidates[0].classifications == ("G06F16/24578", "G06F16/245")


def test_inpadoc_family_keeps_priority_refs_and_derives_dates_separately():
    observation = ProviderObservation(
        observation_id="family-obs",
        action_id="family-a",
        provider_id="provider.epo_ops",
        surface_id="surface.epo_ops.rest",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(
                ArtifactKind.STRUCTURED_RECORD,
                "epo:family-id:42",
                metadata={
                    "source_type": "epo_ops_family",
                    "family_type": "INPADOC_EXTENDED",
                    "definition_version": "ops-family-v3.2",
                    "member_publications": ["EP1A1", "US2A1"],
                    "priority_refs": ["US20240123456@2024-01-10"],
                },
            ),
        ),
        raw_ref=None,
        result_count=1,
        cost={},
        latency_ms=None,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T12:00:00+00:00",
        metadata={},
    )
    family = family_from_observation(observation)
    assert family.priority_refs == ("US20240123456@2024-01-10",)
    assert family.priority_dates == ("2024-01-10",)

    attached = attach_family_identity((_candidate("EP1A1"), _candidate("JP9A")), family)
    folded = fold_candidates_by_family(attached)
    assert tuple(folded.families) == (family.family_id,)
    assert [candidate.publication_number for candidate in folded.unresolved] == ["JP9A"]


def test_priority_chronology_uses_earliest_priority_without_confusing_publication_date():
    entries = build_priority_chronology(
        (
            _candidate("EP1A1", ("2024-02-01", "2024-01-10")),
            _candidate("EP2A1", ("2025-01-10",)),
            _candidate("EP3A1"),
        ),
        cutoff="2024-06-01",
    )
    assert entries[0].earliest_priority == "2024-01-10"
    assert entries[0].cutoff_relation is CutoffRelation.BEFORE_OR_ON
    assert entries[1].cutoff_relation is CutoffRelation.AFTER
    assert entries[2].cutoff_relation is CutoffRelation.UNKNOWN


def test_identity_coverage_surfaces_family_priority_and_unsearched_axes():
    c1 = _candidate("EP1A1", ("2024-01-10",), family_id="fam1")
    c2 = _candidate("JP2A1")
    analysis = analyze_identity_coverage(
        _task(),
        candidates=(c1, c2),
        family_fold=PatentFamilyFoldResult(families={"fam1": (c1,)}, unresolved=(c2,)),
        required_feature_ids=("feature.1", "feature.2"),
        searched_feature_ids=("feature.1",),
        searched_classifications=("G06F16/00",),
        searched_jurisdictions=("EP",),
        searched_languages=("en",),
        searched_methods=("method.lexical_search", "method.patent.classification_search"),
        searched_providers=("provider.epo_ops",),
        npl_searched=False,
        backward_citations_searched=False,
        forward_citations_searched=False,
        counter_path_searched=False,
    )
    gaps = set(analysis.gaps)
    assert {
        PatentGapType.FEATURE_UNSEARCHED,
        PatentGapType.CLASSIFICATION_UNSEARCHED,
        PatentGapType.JURISDICTION_UNSEARCHED,
        PatentGapType.LANGUAGE_UNSEARCHED,
        PatentGapType.FAMILY_UNRESOLVED,
        PatentGapType.PRIORITY_UNRESOLVED,
        PatentGapType.NPL_UNSEARCHED,
        PatentGapType.CITATION_BACKWARD_UNSEARCHED,
        PatentGapType.CITATION_FORWARD_UNSEARCHED,
        PatentGapType.COUNTER_PATH_UNSEARCHED,
    }.issubset(gaps)
