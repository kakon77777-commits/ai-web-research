from ai_web_research.methods.corpus import MethodLifecycle
from ai_web_research.methods.corpus_builtin import build_builtin_method_corpus
from ai_web_research.methods.coverage import CORE_METHOD_IDS_V1, compute_method_coverage


def test_v1_core_method_target_is_provider_neutral_and_domain_neutral():
    assert CORE_METHOD_IDS_V1 == (
        "method.lexical_search", "method.exact_search", "method.query_divergence",
        "method.identity_search", "method.entity_search", "method.classification_search",
        "method.backward_citation", "method.forward_citation", "method.counter_evidence_search",
        "method.temporal_version_search", "method.relation_resolve", "method.fetch_document",
        "method.extract_candidate_evidence",
    )
    assert all("patent." not in method_id for method_id in CORE_METHOD_IDS_V1)


def test_core_method_coverage_reports_current_v03_readiness_honestly():
    report = compute_method_coverage(build_builtin_method_corpus().snapshot(), CORE_METHOD_IDS_V1)
    assert report.required_method_ids == CORE_METHOD_IDS_V1
    assert report.execution_ready_ids == (
        "method.extract_candidate_evidence", "method.fetch_document", "method.identity_search",
        "method.lexical_search", "method.query_divergence",
    )
    assert report.experimental_ids == ("method.counter_evidence_search",)
    assert report.documented_only_ids == (
        "method.backward_citation", "method.classification_search", "method.entity_search",
        "method.exact_search", "method.forward_citation", "method.relation_resolve",
        "method.temporal_version_search",
    )
    assert report.missing_ids == ()
    assert report.deprecated_ids == ()
    assert report.documented_count == 13
    assert report.execution_ready_count == 5
    assert report.documented_ratio == 1.0
    assert report.execution_ready_ratio == 5 / 13


def test_method_coverage_distinguishes_missing_and_deprecated_entries():
    from ai_web_research.methods.corpus import MethodCorpusEntry, SearchMethodCorpus
    corpus = build_builtin_method_corpus()
    base = corpus.get("method.lexical_search")
    custom = SearchMethodCorpus()
    custom.register(base)
    custom.register(MethodCorpusEntry(**{
        **base.__dict__, "method_id": "method.old", "canonical_name": "Old",
        "lifecycle": MethodLifecycle.DEPRECATED, "spec_ref": None,
    }))
    report = compute_method_coverage(custom.snapshot(), ("method.lexical_search", "method.old", "method.absent"))
    assert report.execution_ready_ids == ("method.lexical_search",)
    assert report.deprecated_ids == ("method.old",)
    assert report.missing_ids == ("method.absent",)
    assert report.documented_count == 2
    assert report.execution_ready_count == 1
    assert report.documented_ratio == 2 / 3
    assert report.execution_ready_ratio == 1 / 3


def test_method_coverage_classification_is_deterministic_even_if_required_input_order_changes():
    snapshot = build_builtin_method_corpus().snapshot()
    left = compute_method_coverage(snapshot, ("method.fetch_document", "method.lexical_search", "method.exact_search"))
    right = compute_method_coverage(snapshot, ("method.exact_search", "method.fetch_document", "method.lexical_search"))
    assert left.execution_ready_ids == right.execution_ready_ids
    assert left.documented_only_ids == right.documented_only_ids
    assert left.missing_ids == right.missing_ids
    assert left.execution_ready_ratio == right.execution_ready_ratio
