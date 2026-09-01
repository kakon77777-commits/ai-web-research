from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps

from ai_web_research.core.types import VersionRef
from ai_web_research.methods.registry import MethodRegistrySnapshot
from .spec import MethodBinding, ProviderSpec, ProviderSurface


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset, tuple)):
        return sorted((_canonical(v) for v in value), key=str)
    if hasattr(value, "__dataclass_fields__"):
        return {name: _canonical(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


class ProviderRegistryVersionConflict(ValueError):
    pass


class BindingValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderRegistrySnapshot:
    snapshot_id: str
    providers: tuple[ProviderSpec, ...]
    bindings: tuple[MethodBinding, ...]

    def get_provider(self, ref: VersionRef) -> ProviderSpec:
        for spec in self.providers:
            if spec.provider_id == ref.id and spec.version == ref.version:
                return spec
        raise KeyError((ref.id, ref.version))

    def get_binding(self, binding_id: str) -> MethodBinding:
        for binding in self.bindings:
            if binding.binding_id == binding_id:
                return binding
        raise KeyError(binding_id)

    def surface(self, provider_ref: VersionRef, surface_id: str) -> ProviderSurface:
        provider = self.get_provider(provider_ref)
        for surface in provider.surfaces:
            if surface.surface_id == surface_id:
                return surface
        raise KeyError(surface_id)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[str, str], ProviderSpec] = {}
        self._bindings: dict[str, MethodBinding] = {}

    def register_provider(self, spec: ProviderSpec) -> None:
        key = (spec.provider_id, spec.version)
        existing = self._providers.get(key)
        if existing is None:
            self._providers[key] = spec
            return
        if existing != spec:
            raise ProviderRegistryVersionConflict(f"conflicting provider registration for {key}")

    def register_binding(self, binding: MethodBinding, methods: MethodRegistrySnapshot) -> None:
        existing = self._bindings.get(binding.binding_id)
        if existing is not None:
            if existing != binding:
                raise ProviderRegistryVersionConflict(f"conflicting binding registration for {binding.binding_id}")
            return

        try:
            method = methods.get(binding.method_ref)
        except KeyError as exc:
            raise BindingValidationError(f"unknown method {binding.method_ref}") from exc

        try:
            provider = self._providers[(binding.provider_ref.id, binding.provider_ref.version)]
        except KeyError as exc:
            raise BindingValidationError(f"unknown provider {binding.provider_ref}") from exc

        surface = next((s for s in provider.surfaces if s.surface_id == binding.surface_id), None)
        if surface is None:
            raise BindingValidationError(f"surface {binding.surface_id!r} does not exist on {provider.provider_id}")

        missing = method.required_capabilities - surface.capabilities
        if missing:
            raise BindingValidationError(
                f"surface {surface.surface_id!r} is missing required capabilities: {sorted(missing)}"
            )
        self._bindings[binding.binding_id] = binding

    def get_provider(self, ref: VersionRef) -> ProviderSpec:
        return self._providers[(ref.id, ref.version)]

    def get_binding(self, binding_id: str) -> MethodBinding:
        return self._bindings[binding_id]

    def bindings_for_method(self, ref: VersionRef) -> tuple[MethodBinding, ...]:
        return tuple(
            sorted(
                (b for b in self._bindings.values() if b.method_ref == ref and b.enabled),
                key=lambda b: b.binding_id,
            )
        )

    def snapshot(self) -> ProviderRegistrySnapshot:
        providers = tuple(sorted(self._providers.values(), key=lambda p: (p.provider_id, p.version)))
        bindings = tuple(sorted(self._bindings.values(), key=lambda b: b.binding_id))
        encoded = dumps(
            {"providers": providers, "bindings": bindings},
            default=_canonical,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return ProviderRegistrySnapshot(
            snapshot_id=sha256(encoded).hexdigest(),
            providers=providers,
            bindings=bindings,
        )
