from dataclasses import FrozenInstanceError

import pytest

from ai_web_research.core.types import VersionRef
from ai_web_research.methods.corpus import (
    MethodCorpusConflict,
    MethodCorpusEntry,
    MethodLifecycle,
    MethodReference,
    SearchMethodCorpus,
)


def entry(method_id: str, *, lifecycle=MethodLifecycle.DOCUMENTED) -> MethodCorpusEntry:
    return MethodCorpusEntry(
        method_id=method_id,
        canonical_name=method_id.removeprefix("method."),
        lifecycle=lifecycle,
        aliases=(),
        domain="core",
        purpose="test purpose",
        history="test history",
        goals=("discover",),
        provider_requirements=("capability.lexical",),
        composition_predecessors=(),
        composition_successors=(),
        failure_modes=("no useful candidates",),
        references=(MethodReference("ref.test", "Test Reference"),),
        spec_ref=None,
        notes=(),
    )


def test_method_lifecycle_has_canonical_maturity_states():
    assert [state.value for state in MethodLifecycle] == [
        "documented",
        "experimental",
        "executable",
        "validated",
        "deprecated",
    ]


def test_corpus_entry_is_immutable():
    item = entry("method.example")
    with pytest.raises(FrozenInstanceError):
        item.method_id = "method.changed"


def test_identical_registration_is_idempotent_but_conflict_fails_closed():
    corpus = SearchMethodCorpus()
    item = entry("method.example")
    corpus.register(item)
    corpus.register(item)
    assert corpus.list() == (item,)

    conflicting = MethodCorpusEntry(
        **{**item.__dict__, "purpose": "different purpose"}
    )
    with pytest.raises(MethodCorpusConflict):
        corpus.register(conflicting)


def test_snapshot_is_sorted_and_registration_order_independent():
    a = entry("method.alpha")
    z = entry("method.zeta", lifecycle=MethodLifecycle.EXECUTABLE)

    left = SearchMethodCorpus()
    left.register(z)
    left.register(a)

    right = SearchMethodCorpus()
    right.register(a)
    right.register(z)

    left_snapshot = left.snapshot()
    right_snapshot = right.snapshot()

    assert [e.method_id for e in left_snapshot.entries] == ["method.alpha", "method.zeta"]
    assert left_snapshot.entries == right_snapshot.entries
    assert left_snapshot.snapshot_id == right_snapshot.snapshot_id
    assert left_snapshot.get("method.alpha") == a


def test_executable_entry_can_link_to_versioned_runtime_spec():
    item = MethodCorpusEntry(
        **{
            **entry("method.lexical_search", lifecycle=MethodLifecycle.VALIDATED).__dict__,
            "spec_ref": VersionRef("method.lexical_search", "1.0.0"),
        }
    )
    assert item.spec_ref == VersionRef("method.lexical_search", "1.0.0")
