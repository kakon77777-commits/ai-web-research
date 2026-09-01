
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
    publication = PatentIdentifier(
        identifier_type=PatentIdentifierType.PUBLICATION,
        authority="EP",
        value="EP 1234567 A1",
        normalized_value="EP1234567A1",
    )
    application = PatentIdentifier(
        identifier_type=PatentIdentifierType.APPLICATION,
        authority="EP",
        value="EP 01234567.8",
        normalized_value="EP01234567.8",
    )
    assert publication.identifier_type is not application.identifier_type
    assert publication.normalized_value == "EP1234567A1"


def test_classification_identity_requires_scheme_symbol_and_version():
    cpc = ClassificationIdentity(
        scheme=ClassificationScheme.CPC,
        symbol="G06F40/30",
        version="2026.05",
        title="Semantic analysis",
        definition_ref=None,
        parent_symbols=("G06F40/00",),
        effective_at="2026-05-01",
    )
    assert cpc.scheme is ClassificationScheme.CPC
    assert cpc.version == "2026.05"


def test_feature_and_concept_keep_search_representation_distinct():
    feature = InventionFeature(
        feature_id="feature.1",
        description="Use a model to expand a research query into independent search branches.",
        function="query expansion",
        mechanism="model-generated divergent branches",
        input_state="research question",
        output_state="query set",
        constraints=("independent branches",),
        dependencies=(),
        importance=1.0,
        novelty_hypothesis="branch diversity",
        metadata={},
    )
    concept = PatentConcept(
        concept_id="concept.1",
        feature_refs=(feature.feature_id,),
        functional_terms=("query expansion", "query diversification"),
        structural_terms=(),
        mechanism_terms=("language model", "branch generation"),
        patent_style_terms=("generating a plurality of search queries",),
        historical_terms=("query reformulation",),
        synonyms=("search diversification",),
        broader_terms=("information retrieval",),
        narrower_terms=(),
        translations={"de": ("Suchanfrageerweiterung",)},
        classification_hints=("G06F16/00",),
        metadata={},
    )
    assert concept.feature_refs == ("feature.1",)
    assert feature.description not in concept.patent_style_terms


def test_family_priority_and_candidate_are_not_collapsed_into_one_identity():
    family = PatentFamilyIdentity(
        family_id="family.docdb.1",
        family_type="DOCDB_SIMPLE",
        provider="EPO",
        definition_version="2026",
        member_publications=("EP123A1", "US456B2"),
        priority_refs=("priority.1",),
    )
    priority = PriorityClaim(
        priority_id="priority.1",
        application_number="US123",
        jurisdiction="US",
        filing_date="2020-01-01",
        relationship="priority",
        source_refs=("epo:record:1",),
    )
    candidate = PatentCandidate(
        candidate_id="candidate.ep.1",
        publication_number="EP123A1",
        application_number=None,
        family_id=family.family_id,
        title="Example",
        abstract=None,
        classifications=("G06F16/00",),
        priority_dates=(priority.filing_date,),
        publication_date="2021-01-01",
        applicant_refs=(),
        inventor_refs=(),
        retrieval_score=None,
        score_semantics="epo_ops_provider_order",
        provider_refs=("provider.epo_ops",),
        metadata={},
    )
    assert candidate.publication_number != family.family_id
    assert family.member_publications[0] == candidate.publication_number


def test_patent_coverage_and_gap_types_are_multiaxial():
    coverage = PatentCoverageState(
        feature_coverage={"feature.1": "searched"},
        classification_coverage={"G06F16/00": "searched"},
        jurisdiction_coverage={"EP": "searched", "JP": "unsearched"},
        language_coverage={"en": "searched", "ja": "unsearched"},
        chronology_coverage={"priority": "partial"},
        citation_coverage={"backward": "unsearched"},
        npl_coverage={"academic": "unsearched"},
        provider_coverage={"provider.epo_ops": "searched"},
        method_coverage={"method.lexical_search": "searched"},
    )
    assert coverage.jurisdiction_coverage["JP"] == "unsearched"
    assert PatentGapType.JURISDICTION_UNSEARCHED.value == "jurisdiction_unsearched"
    assert PatentGapType.NPL_UNSEARCHED.value == "npl_unsearched"


def test_patent_task_extension_preserves_declared_scope_and_review_gate():
    task = PatentSearchTaskExtension(
        task_type="PRIOR_ART_SEARCH",
        target_invention_ref="invention.1",
        target_product_ref=None,
        target_jurisdictions=("EP", "US"),
        target_languages=("en", "de"),
        filing_or_priority_cutoff="2025-01-01",
        publication_cutoff="2025-01-01",
        required_classifications=("G06F16/00",),
        include_npl=True,
        include_citations=True,
        include_legal_status=False,
        recall_target="high",
        verification_profile="prior_art_high",
        human_review_required=True,
        metadata={},
    )
    assert task.target_jurisdictions == ("EP", "US")
    assert task.human_review_required is True
