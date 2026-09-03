from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from json import dumps

from ai_web_research.core.types import VersionRef


class MethodLifecycle(StrEnum):
    DOCUMENTED = "documented"
    EXPERIMENTAL = "experimental"
    EXECUTABLE = "executable"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class MethodReference:
    reference_id: str
    citation: str
    url: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MethodCorpusEntry:
    method_id: str
    canonical_name: str
    lifecycle: MethodLifecycle
    aliases: tuple[str, ...]
    domain: str
    purpose: str
    history: str
    goals: tuple[str, ...]
    provider_requirements: tuple[str, ...]
    composition_predecessors: tuple[str, ...]
    composition_successors: tuple[str, ...]
    failure_modes: tuple[str, ...]
    references: tuple[MethodReference, ...]
    spec_ref: VersionRef | None
    notes: tuple[str, ...]


class MethodCorpusConflict(ValueError):
    pass


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    raise TypeError(type(value).__name__)


@dataclass(frozen=True)
class MethodCorpusSnapshot:
    snapshot_id: str
    entries: tuple[MethodCorpusEntry, ...]

    def get(self, method_id: str) -> MethodCorpusEntry:
        for entry in self.entries:
            if entry.method_id == method_id:
                return entry
        raise KeyError(method_id)


class SearchMethodCorpus:
    def __init__(self) -> None:
        self._entries: dict[str, MethodCorpusEntry] = {}

    def register(self, entry: MethodCorpusEntry) -> None:
        existing = self._entries.get(entry.method_id)
        if existing is None:
            self._entries[entry.method_id] = entry
            return
        if existing != entry:
            raise MethodCorpusConflict(
                f"conflicting method corpus registration for {entry.method_id}"
            )

    def get(self, method_id: str) -> MethodCorpusEntry:
        return self._entries[method_id]

    def list(self) -> tuple[MethodCorpusEntry, ...]:
        return tuple(sorted(self._entries.values(), key=lambda entry: entry.method_id))

    def snapshot(self) -> MethodCorpusSnapshot:
        entries = self.list()
        encoded = dumps(
            _canonical(entries), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return MethodCorpusSnapshot(
            snapshot_id=sha256(encoded).hexdigest(),
            entries=entries,
        )
