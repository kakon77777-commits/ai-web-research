from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AuthorizedAction, ExecutionContext, ProviderObservation


@runtime_checkable
class ProviderAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    async def execute(
        self,
        action: AuthorizedAction,
        context: ExecutionContext,
    ) -> ProviderObservation: ...


class AdapterVersionConflict(ValueError):
    pass


class AdapterNotFound(KeyError):
    pass


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        key = (adapter.adapter_id, adapter.adapter_version)
        existing = self._adapters.get(key)
        if existing is None:
            self._adapters[key] = adapter
            return
        if existing is not adapter:
            raise AdapterVersionConflict(f"conflicting adapter registration for {key}")

    def get(self, adapter_id: str, adapter_version: str) -> ProviderAdapter:
        try:
            return self._adapters[(adapter_id, adapter_version)]
        except KeyError as exc:
            raise AdapterNotFound((adapter_id, adapter_version)) from exc

    def list(self) -> tuple[ProviderAdapter, ...]:
        return tuple(self._adapters[key] for key in sorted(self._adapters))
