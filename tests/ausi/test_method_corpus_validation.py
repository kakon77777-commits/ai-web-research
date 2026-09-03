from ai_web_research.core.types import VersionRef
from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.domains.patents.prior_art_methods import register_prior_art_methods
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.corpus import MethodCorpusEntry, MethodLifecycle, SearchMethodCorpus
from ai_web_research.methods.corpus_builtin import build_builtin_method_corpus
from ai_web_research.methods.corpus_validation import validate_corpus_against_registry
from ai_web_research.methods.registry import SearchMethodRegistry


def full_method_registry_snapshot():
    registry = SearchMethodRegistry()
    register_builtin_methods(registry)
    register_patent_methods(registry)
    register_prior_art_methods(registry)
    return registry.snapshot()


def test_builtin_corpus_is_consistent_with_current_full_runtime_registry():
    issues = validate_corpus_against_registry(
        build_builtin_method_corpus().snapshot(),
        full_method_registry_snapshot(),
    )
    assert issues == ()


def test_validated_or_executable_entry_requires_spec_ref():
    base = build_builtin_method_corpus().get("method.lexical_search")
    corpus = SearchMethodCorpus()
    corpus.register(MethodCorpusEntry(**{**base.__dict__, "spec_ref": None}))
    issues = validate_corpus_against_registry(corpus.snapshot(), full_method_registry_snapshot())
    assert [(issue.method_id, issue.code) for issue in issues] == [
        ("method.lexical_search", "MISSING_SPEC_REF")
    ]


def test_execution_ready_entry_requires_registered_spec():
    base = build_builtin_method_corpus().get("method.lexical_search")
    corpus = SearchMethodCorpus()
    corpus.register(MethodCorpusEntry(**{
        **base.__dict__,
        "method_id": "method.imaginary",
        "canonical_name": "Imaginary",
        "spec_ref": VersionRef("method.imaginary", "1.0.0"),
    }))
    issues = validate_corpus_against_registry(corpus.snapshot(), full_method_registry_snapshot())
    assert [(issue.method_id, issue.code) for issue in issues] == [
        ("method.imaginary", "SPEC_NOT_REGISTERED")
    ]


def test_execution_ready_entry_cannot_point_to_unavailable_runtime_spec():
    semantic = build_builtin_method_corpus().get("method.semantic_search")
    corpus = SearchMethodCorpus()
    corpus.register(MethodCorpusEntry(**{
        **semantic.__dict__,
        "lifecycle": MethodLifecycle.EXECUTABLE,
    }))
    issues = validate_corpus_against_registry(corpus.snapshot(), full_method_registry_snapshot())
    assert [(issue.method_id, issue.code) for issue in issues] == [
        ("method.semantic_search", "RUNTIME_NOT_EXECUTABLE")
    ]


def test_spec_ref_id_must_match_corpus_method_identity():
    base = build_builtin_method_corpus().get("method.lexical_search")
    corpus = SearchMethodCorpus()
    corpus.register(MethodCorpusEntry(**{
        **base.__dict__,
        "spec_ref": VersionRef("method.fetch_document", "1.0.0"),
    }))
    issues = validate_corpus_against_registry(corpus.snapshot(), full_method_registry_snapshot())
    assert [(issue.method_id, issue.code) for issue in issues] == [
        ("method.lexical_search", "SPEC_REF_ID_MISMATCH")
    ]


def test_documented_method_may_have_no_executable_spec():
    exact = build_builtin_method_corpus().get("method.exact_search")
    corpus = SearchMethodCorpus()
    corpus.register(exact)
    assert validate_corpus_against_registry(corpus.snapshot(), full_method_registry_snapshot()) == ()
