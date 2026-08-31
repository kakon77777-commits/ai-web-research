from ai_web_research.domains.patents.models import (
    ClassificationIdentity,
    ClassificationScheme,
    InventionFeature,
    PatentCandidate,
    PatentConcept,
    PatentCoverageState,
    PatentFamilyIdentity,
    PatentGapType,
    PatentIdentifier,
    PatentIdentifierType,
    PatentSearchTaskExtension,
    PriorityClaim,
)


def test_patent_identifier_keeps_type_authority_raw_and_normalized_value_separate():
    publication = PatentIdentifier(PatentIdentifierType.PUBLICATION, "EP", "EP 1234567 A1", "EP1234567A1")
    application = PatentIdentifier(PatentIdentifierType.APPLICATION, "EP", "EP 01234567.8", "EP01234567.8")
    assert publication.identifier_type is not application.identifier_type
    assert publication.normalized_value == "EP1234567A1"


def test_classification_identity_requires_scheme_symbol_and_version():
    cpc = ClassificationIdentity(ClassificationScheme.CPC, "G06F40/30", "2026.05", "Semantic analysis", None, ("G06F40/00",), "2026-05-01")
    assert cpc.scheme is ClassificationScheme.CPC
    assert cpc.version == "2026.05"


def test_feature_and_concept_keep_search_representation_distinct():
    feature = InventionFeature("feature.1", "Use a model to expand a research query into independent search branches.", "query expansion", "model-generated divergent branches", "research question", "query set", ("independent branches",), (), 1.0, "branch diversity", {})
    concept = PatentConcept("concept.1", (feature.feature_id,), ("query expansion", "query diversification"), (), ("language model", "branch generation"), ("generating a plurality of search queries",), ("query reformulation",), ("search diversification",), ("information retrieval",), (), {"de": ("Suchanfrageerweiterung",)}, ("G06F16/00",), {})
    assert concept.feature_refs == ("feature.1",)
    assert feature.description not in concept.patent_style_terms


def test_family_priority_and_candidate_are_not_collapsed_into_one_identity():
    family = PatentFamilyIdentity("family.docdb.1", "DOCDB_SIMPLE", "EPO", "2026", ("EP123A1", "US456B2"), ("priority.1",))
    priority = PriorityClaim("priority.1", "US123", "US", "2020-01-01", "priority", ("epo:record:1",))
    candidate = PatentCandidate("candidate.ep.1", "EP123A1", None, family.family_id, "Example", None, ("G06F16/00",), (priority.filing_date,), "2021-01-01", (), (), None, "epo_ops_provider_order", ("provider.epo_ops",), {})
    assert candidate.publication_number != family.family_id
    assert family.member_publications[0] == candidate.publication_number


def test_patent_coverage_and_gap_types_are_multiaxial():
    coverage = PatentCoverageState({"feature.1": "searched"}, {"G06F16/00": "searched"}, {"EP": "searched", "JP": "unsearched"}, {"en": "searched", "ja": "unsearched"}, {"priority": "partial"}, {"backward": "unsearched"}, {"academic": "unsearched"}, {"provider.epo_ops": "searched"}, {"method.lexical_search": "searched"})
    assert coverage.jurisdiction_coverage["JP"] == "unsearched"
    assert PatentGapType.JURISDICTION_UNSEARCHED.value == "jurisdiction_unsearched"
    assert PatentGapType.NPL_UNSEARCHED.value == "npl_unsearched"


def test_patent_task_extension_preserves_declared_scope_and_review_gate():
    task = PatentSearchTaskExtension("PRIOR_ART_SEARCH", "invention.1", None, ("EP", "US"), ("en", "de"), "2025-01-01", "2025-01-01", ("G06F16/00",), True, True, False, "high", "prior_art_high", True, {})
    assert task.target_jurisdictions == ("EP", "US")
    assert task.human_review_required is True
