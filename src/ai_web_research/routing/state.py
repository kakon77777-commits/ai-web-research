from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from json import dumps

from ai_web_research.core.types import VersionRef
from .models import ProviderState


class ProviderStateSemanticConflict(ValueError):
    pass


class StaleProviderStateObservation(ValueError):
    pass


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(v) for v in value), key=str)
    if hasattr(value, "__dataclass_fields__"):
        return {name: _canonical(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


def _timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ProviderState.last_checked_at: {value!r}") from exc


@dataclass(frozen=True)
class ProviderStateSnapshot:
    snapshot_id: str
    states: tuple[ProviderState, ...]

    def get(self, provider_ref: VersionRef, surface_id: str) -> ProviderState:
        key = (provider_ref.id, provider_ref.version, surface_id)
        for state in self.states:
            if state.key == key:
                return state
        raise KeyError(key)

    def maybe_get(self, provider_ref: VersionRef, surface_id: str) -> ProviderState | None:
        try:
            return self.get(provider_ref, surface_id)
        except KeyError:
            return None


class ProviderStateRegistry:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str, str], ProviderState] = {}

    def observe(self, state: ProviderState) -> None:
        _timestamp(state.last_checked_at)
        existing = self._states.get(state.key)
        if existing is None:
            self._states[state.key] = state
            return
        existing_time = _timestamp(existing.last_checked_at)
        incoming_time = _timestamp(state.last_checked_at)
        if incoming_time < existing_time:
            raise StaleProviderStateObservation(
                f"stale state observation for {state.key}: {state.last_checked_at} < {existing.last_checked_at}"
            )
        if incoming_time == existing_time:
            if existing == state:
                return
            raise ProviderStateSemanticConflict(
                f"conflicting provider state for {state.key} at {state.last_checked_at}"
            )
        self._states[state.key] = state

    def snapshot(self) -> ProviderStateSnapshot:
        states = tuple(sorted(self._states.values(), key=lambda state: state.key))
        encoded = dumps(_canonical(states), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return ProviderStateSnapshot(snapshot_id=sha256(encoded).hexdigest(), states=states)
