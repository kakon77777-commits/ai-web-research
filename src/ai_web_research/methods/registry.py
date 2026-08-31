from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps

from ai_web_research.core.types import VersionRef
from .spec import SearchMethodSpec


class RegistryVersionConflict(ValueError):
    pass


def _semver_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise ValueError(f"unsupported semantic version: {version}") from exc


def _json_default(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_default(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_default(v) for v in value]
    if isinstance(value, (set, frozenset, tuple)):
        return sorted((_json_default(v) for v in value), key=str)
    if hasattr(value, "__dataclass_fields__"):
        return {name: _json_default(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


@dataclass(frozen=True)
class MethodRegistrySnapshot:
    snapshot_id: str
    methods: tuple[SearchMethodSpec, ...]

    def get(self, ref: VersionRef) -> SearchMethodSpec:
        for spec in self.methods:
            if spec.method_id == ref.id and spec.version == ref.version:
                return spec
        raise KeyError((ref.id, ref.version))


class SearchMethodRegistry:
    def __init__(self) -> None:
        self._specs: dict[tuple[str, str], SearchMethodSpec] = {}

    def register(self, spec: SearchMethodSpec) -> None:
        key = (spec.method_id, spec.version)
        existing = self._specs.get(key)
        if existing is None:
            self._specs[key] = spec
            return
        if existing != spec:
            raise RegistryVersionConflict(f"conflicting method registration for {key}")

    def get(self, ref: VersionRef) -> SearchMethodSpec:
        return self._specs[(ref.id, ref.version)]

    def latest(self, method_id: str) -> SearchMethodSpec:
        matches = [spec for (mid, _), spec in self._specs.items() if mid == method_id]
        if not matches:
            raise KeyError(method_id)
        return max(matches, key=lambda spec: _semver_key(spec.version))

    def list(self) -> tuple[SearchMethodSpec, ...]:
        return tuple(sorted(self._specs.values(), key=lambda spec: (spec.method_id, _semver_key(spec.version))))

    def snapshot(self) -> MethodRegistrySnapshot:
        methods = self.list()
        encoded = dumps(methods, default=_json_default, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return MethodRegistrySnapshot(snapshot_id=sha256(encoded).hexdigest(), methods=methods)
