from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue, VersionRef
from ai_web_research.providers.spec import ProviderTopology


class ProviderAvailability(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PolicyFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderState:
    provider_ref: VersionRef
    surface_id: str
    availability: ProviderAvailability
    healthy: bool | None
    credential_available: bool | None
    quota_remaining: float | None
    quota_reset_at: str | None
    estimated_cost: float | None
    estimated_latency_ms: float | None
    policy_freshness: PolicyFreshness
    runtime_capabilities: frozenset[str]
    model_available: bool | None
    last_checked_at: str
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        sensitive_markers = (
            "api_key",
            "access_token",
            "refresh_token",
            "client_secret",
            "private_key",
            "password",
            "credential_value",
        )

        def validate(value, path: str = "metadata") -> None:
            if isinstance(value, dict):
                for raw_key, nested in value.items():
                    key = str(raw_key).lower().replace("-", "_")
                    if any(marker in key for marker in sensitive_markers):
                        raise ValueError(f"sensitive metadata key is not allowed in ProviderState: {path}.{raw_key}")
                    validate(nested, f"{path}.{raw_key}")
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    validate(nested, f"{path}[{index}]")

        validate(self.metadata)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.provider_ref.id, self.provider_ref.version, self.surface_id)


@dataclass(frozen=True)
class RoutingPolicy:
    policy_id: str
    preferred_binding_ids: tuple[str, ...] = ()
    preferred_provider_ids: tuple[str, ...] = ()
    preferred_topologies: tuple[ProviderTopology, ...] = ()
    allow_degraded: bool = False
    allow_unknown_state: bool = False
    require_fresh_policy_state: bool = True
    require_credential_for_authenticated: bool = True
    require_model_available: bool = True
    max_estimated_cost: float | None = None
    max_estimated_latency_ms: float | None = None
    required_runtime_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoutingCandidateEvaluation:
    binding_id: str
    provider_ref: VersionRef
    surface_id: str
    eligible: bool
    reason_codes: tuple[str, ...]
    availability: ProviderAvailability | None
    credential_available: bool | None
    quota_remaining: float | None
    estimated_cost: float | None
    estimated_latency_ms: float | None
    policy_freshness: PolicyFreshness | None
    model_available: bool | None

    def to_receipt_metadata(self) -> dict[str, JsonValue]:
        return {
            "binding_id": self.binding_id,
            "provider_ref": {"id": self.provider_ref.id, "version": self.provider_ref.version},
            "surface_id": self.surface_id,
            "eligible": self.eligible,
            "reason_codes": list(self.reason_codes),
            "availability": self.availability.value if self.availability is not None else None,
            "credential_available": self.credential_available,
            "quota_remaining": self.quota_remaining,
            "estimated_cost": self.estimated_cost,
            "estimated_latency_ms": self.estimated_latency_ms,
            "policy_freshness": self.policy_freshness.value if self.policy_freshness is not None else None,
            "model_available": self.model_available,
        }


@dataclass(frozen=True)
class RoutingDecision:
    method_ref: VersionRef
    routing_policy_id: str
    provider_registry_snapshot_id: str
    provider_state_snapshot_id: str
    selected_binding_id: str | None
    selected_provider_ref: VersionRef | None
    selected_surface_id: str | None
    candidates: tuple[RoutingCandidateEvaluation, ...]
    reason_codes: tuple[str, ...]

    def to_receipt_metadata(self) -> dict[str, JsonValue]:
        return {
            "method_ref": {"id": self.method_ref.id, "version": self.method_ref.version},
            "routing_policy_id": self.routing_policy_id,
            "provider_registry_snapshot_id": self.provider_registry_snapshot_id,
            "provider_state_snapshot_id": self.provider_state_snapshot_id,
            "selected_binding_id": self.selected_binding_id,
            "selected_provider_ref": (
                {"id": self.selected_provider_ref.id, "version": self.selected_provider_ref.version}
                if self.selected_provider_ref is not None
                else None
            ),
            "selected_surface_id": self.selected_surface_id,
            "reason_codes": list(self.reason_codes),
            "candidates": [candidate.to_receipt_metadata() for candidate in self.candidates],
        }
