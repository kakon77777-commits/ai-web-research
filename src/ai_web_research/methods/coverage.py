from __future__ import annotations

from dataclasses import dataclass

from .corpus import MethodCorpusSnapshot, MethodLifecycle


CORE_METHOD_IDS_V1 = (
    "method.lexical_search",
    "method.exact_search",
    "method.query_divergence",
    "method.identity_search",
    "method.entity_search",
    "method.classification_search",
    "method.backward_citation",
    "method.forward_citation",
    "method.counter_evidence_search",
    "method.temporal_version_search",
    "method.relation_resolve",
    "method.fetch_document",
    "method.extract_candidate_evidence",
)


@dataclass(frozen=True)
class MethodCoverageReport:
    required_method_ids: tuple[str, ...]
    documented_ids: tuple[str, ...]
    execution_ready_ids: tuple[str, ...]
    experimental_ids: tuple[str, ...]
    documented_only_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    deprecated_ids: tuple[str, ...]
    documented_count: int
    execution_ready_count: int
    documented_ratio: float
    execution_ready_ratio: float


def compute_method_coverage(
    corpus: MethodCorpusSnapshot,
    required_method_ids: tuple[str, ...],
) -> MethodCoverageReport:
    required = tuple(dict.fromkeys(required_method_ids))
    by_id = {entry.method_id: entry for entry in corpus.entries}

    documented: list[str] = []
    execution_ready: list[str] = []
    experimental: list[str] = []
    documented_only: list[str] = []
    missing: list[str] = []
    deprecated: list[str] = []

    for method_id in required:
        entry = by_id.get(method_id)
        if entry is None:
            missing.append(method_id)
            continue
        documented.append(method_id)
        if entry.lifecycle in {MethodLifecycle.EXECUTABLE, MethodLifecycle.VALIDATED}:
            execution_ready.append(method_id)
        elif entry.lifecycle is MethodLifecycle.EXPERIMENTAL:
            experimental.append(method_id)
        elif entry.lifecycle is MethodLifecycle.DOCUMENTED:
            documented_only.append(method_id)
        elif entry.lifecycle is MethodLifecycle.DEPRECATED:
            deprecated.append(method_id)

    total = len(required)
    documented_count = len(documented)
    execution_ready_count = len(execution_ready)
    return MethodCoverageReport(
        required_method_ids=required,
        documented_ids=tuple(sorted(documented)),
        execution_ready_ids=tuple(sorted(execution_ready)),
        experimental_ids=tuple(sorted(experimental)),
        documented_only_ids=tuple(sorted(documented_only)),
        missing_ids=tuple(sorted(missing)),
        deprecated_ids=tuple(sorted(deprecated)),
        documented_count=documented_count,
        execution_ready_count=execution_ready_count,
        documented_ratio=(documented_count / total if total else 1.0),
        execution_ready_ratio=(execution_ready_count / total if total else 1.0),
    )
