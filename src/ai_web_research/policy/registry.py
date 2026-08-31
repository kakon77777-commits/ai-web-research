from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps

from .models import SourcePolicyProfile


class PolicyRegistryVersionConflict(ValueError):
    pass


def _semver_key(version: str) -> tuple:
    parts = version.split(".")
    key = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        key.append(int(digits or 0))
    return tuple(key)


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_canonical(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _canonical(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


@dataclass(frozen=True)
class PolicyRegistrySnapshot:
    snapshot_id: str
    profiles: tuple[SourcePolicyProfile, ...]

    def profiles_for(self, provider_id: str, surface_id: str) -> tuple[SourcePolicyProfile, ...]:
        matching = [
            p for p in self.profiles
            if p.provider_id == provider_id and p.surface_id == surface_id
        ]
        latest: dict[str, SourcePolicyProfile] = {}
        for profile in matching:
            current = latest.get(profile.policy_id)
            if current is None or _semver_key(profile.version) > _semver_key(current.version):
                latest[profile.policy_id] = profile
        return tuple(sorted(latest.values(), key=lambda p: p.policy_id))


class SourcePolicyRegistry:
    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], SourcePolicyProfile] = {}

    def register(self, profile: SourcePolicyProfile) -> None:
        key = (profile.policy_id, profile.version)
        existing = self._profiles.get(key)
        if existing is None:
            self._profiles[key] = profile
            return
        if existing != profile:
            raise PolicyRegistryVersionConflict(
                f"conflicting policy registration for {profile.policy_id}@{profile.version}"
            )

    def latest(self, policy_id: str) -> SourcePolicyProfile:
        matches = [p for (pid, _), p in self._profiles.items() if pid == policy_id]
        if not matches:
            raise KeyError(policy_id)
        return max(matches, key=lambda p: _semver_key(p.version))

    def profiles_for(self, provider_id: str, surface_id: str) -> tuple[SourcePolicyProfile, ...]:
        return self.snapshot().profiles_for(provider_id, surface_id)

    def snapshot(self) -> PolicyRegistrySnapshot:
        profiles = tuple(sorted(self._profiles.values(), key=lambda p: (p.policy_id, p.version)))
        encoded = dumps(profiles, default=_canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return PolicyRegistrySnapshot(sha256(encoded).hexdigest(), profiles)
