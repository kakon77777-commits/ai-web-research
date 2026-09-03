from ai_web_research.core.types import VersionRef
from ai_web_research.methods.corpus import MethodLifecycle
from ai_web_research.methods.corpus_builtin import build_builtin_method_corpus


def test_builtin_corpus_has_broad_initial_method_space():
    snapshot = build_builtin_method_corpus().snapshot()
    assert len(snapshot.entries) >= 28
    ids = {entry.method_id for entry in snapshot.entries}
    assert {
        "method.boolean_search", "method.exact_search", "method.phrase_search",
        "method.lexical_search", "method.query_divergence", "method.identity_search",
        "method.entity_search", "method.faceted_search", "method.classification_search",
        "method.semantic_search", "method.backward_citation", "method.forward_citation",
        "method.snowballing", "method.berrypicking", "method.exploratory_search",
        "method.systematic_review_search", "method.counter_evidence_search",
        "method.prior_art_search", "method.temporal_version_search", "method.graph_search",
        "method.cross_language_search", "method.federated_search", "method.adversarial_search",
    }.issubset(ids)


def test_runtime_methods_have_honest_lifecycle_and_spec_links():
    snapshot = build_builtin_method_corpus().snapshot()
    lexical = snapshot.get("method.lexical_search")
    assert lexical.lifecycle is MethodLifecycle.VALIDATED
    assert lexical.spec_ref == VersionRef("method.lexical_search", "1.0.0")
    divergence = snapshot.get("method.query_divergence")
    assert divergence.lifecycle is MethodLifecycle.EXECUTABLE
    assert divergence.spec_ref == VersionRef("method.query_divergence", "1.0.0")
    forward = snapshot.get("method.forward_citation")
    assert forward.lifecycle is MethodLifecycle.DOCUMENTED
    assert forward.spec_ref == VersionRef("method.forward_citation", "1.0.0")
    counter = snapshot.get("method.counter_evidence_search")
    assert counter.lifecycle is MethodLifecycle.EXPERIMENTAL
    assert counter.spec_ref == VersionRef("method.counter_evidence_search", "1.0.0")
    exact = snapshot.get("method.exact_search")
    assert exact.lifecycle is MethodLifecycle.DOCUMENTED
    assert exact.spec_ref is None


def test_human_search_methods_include_references_and_composition_metadata():
    snapshot = build_builtin_method_corpus().snapshot()
    berrypicking = snapshot.get("method.berrypicking")
    assert berrypicking.lifecycle is MethodLifecycle.DOCUMENTED
    assert any("Bates" in ref.citation for ref in berrypicking.references)
    assert "method.query_divergence" in berrypicking.composition_successors
    exploratory = snapshot.get("method.exploratory_search")
    assert any("Marchionini" in ref.citation for ref in exploratory.references)
    systematic = snapshot.get("method.systematic_review_search")
    assert any("PRISMA-S" in ref.citation for ref in systematic.references)
    assert "method.backward_citation" in systematic.composition_successors


def test_domain_methods_remain_domain_scoped():
    snapshot = build_builtin_method_corpus().snapshot()
    classification = snapshot.get("method.patent.classification_search")
    family = snapshot.get("method.patent.family_resolve")
    claims = snapshot.get("method.patent.claims_fetch")
    assert classification.domain == "patent_intelligence"
    assert classification.lifecycle is MethodLifecycle.VALIDATED
    assert classification.spec_ref == VersionRef("method.patent.classification_search", "1.0.0")
    assert family.domain == "patent_intelligence"
    assert family.lifecycle is MethodLifecycle.VALIDATED
    assert claims.lifecycle is MethodLifecycle.EXECUTABLE


def test_builtin_method_ids_and_requirements_are_provider_neutral():
    snapshot = build_builtin_method_corpus().snapshot()
    provider_brands = ("brave", "grok", "gemini", "google", "crossref", "epo")
    for entry in snapshot.entries:
        assert not any(brand in entry.method_id.lower() for brand in provider_brands)
        assert not any(
            brand in requirement.lower()
            for requirement in entry.provider_requirements
            for brand in provider_brands
        )


def test_llm_recall_is_executable_but_explicitly_not_external_evidence():
    recall = build_builtin_method_corpus().snapshot().get("method.llm_recall")
    assert recall.lifecycle is MethodLifecycle.EXECUTABLE
    assert any("not external evidence" in note.lower() for note in recall.notes)
