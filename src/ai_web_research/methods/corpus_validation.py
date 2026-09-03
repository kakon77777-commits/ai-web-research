from __future__ import annotations

from dataclasses import dataclass

from .corpus import MethodCorpusSnapshot, MethodLifecycle
from .registry import MethodRegistrySnapshot
from .spec import MethodAvailability


@dataclass(frozen=True)
class MethodCorpusValidationIssue:
    method_id: str
    code: str
    message: str


_EXECUTION_READY = {MethodLifecycle.EXECUTABLE, MethodLifecycle.VALIDATED}
_RUNTIME_BLOCKED = {MethodAvailability.UNAVAILABLE, MethodAvailability.DEPRECATED}


def validate_corpus_against_registry(
    corpus: MethodCorpusSnapshot,
    registry: MethodRegistrySnapshot,
) -> tuple[MethodCorpusValidationIssue, ...]:
    issues: list[MethodCorpusValidationIssue] = []

    for entry in corpus.entries:
        ref = entry.spec_ref
        if ref is not None and ref.id != entry.method_id:
            issues.append(MethodCorpusValidationIssue(
                method_id=entry.method_id,
                code="SPEC_REF_ID_MISMATCH",
                message=f"spec_ref {ref.id}@{ref.version} does not match corpus method identity",
            ))
            continue

        if entry.lifecycle not in _EXECUTION_READY:
            continue

        if ref is None:
            issues.append(MethodCorpusValidationIssue(
                method_id=entry.method_id,
                code="MISSING_SPEC_REF",
                message="execution-ready corpus entry has no runtime SearchMethodSpec reference",
            ))
            continue

        try:
            spec = registry.get(ref)
        except KeyError:
            issues.append(MethodCorpusValidationIssue(
                method_id=entry.method_id,
                code="SPEC_NOT_REGISTERED",
                message=f"runtime SearchMethodSpec {ref.id}@{ref.version} is not registered",
            ))
            continue

        if spec.availability in _RUNTIME_BLOCKED:
            issues.append(MethodCorpusValidationIssue(
                method_id=entry.method_id,
                code="RUNTIME_NOT_EXECUTABLE",
                message=(
                    f"corpus lifecycle {entry.lifecycle.value} conflicts with runtime "
                    f"availability {spec.availability.value}"
                ),
            ))

    return tuple(sorted(issues, key=lambda issue: (issue.method_id, issue.code)))
