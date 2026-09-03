from __future__ import annotations

from ai_web_research.core.types import JsonValue, VersionRef
from .models import PolicyFreshness, ProviderAvailability, ProviderState


def credential_available_from_services(service_key: str, services: dict[str, object]) -> bool:
    value = services.get(service_key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def observe_surface_state(
    *,
    provider_ref: VersionRef,
    surface_id: str,
    last_checked_at: str,
    credential_service_key: str | None,
    services: dict[str, object],
    availability: ProviderAvailability,
    healthy: bool | None,
    quota_remaining: float | None,
    estimated_cost: float | None,
    estimated_latency_ms: float | None,
    policy_freshness: PolicyFreshness,
    runtime_capabilities: frozenset[str],
    model_available: bool | None,
    quota_reset_at: str | None = None,
    reason_codes: tuple[str, ...] = (),
    metadata: dict[str, JsonValue] | None = None,
) -> ProviderState:
    credential_available = (
        credential_available_from_services(credential_service_key, services)
        if credential_service_key is not None
        else None
    )
    return ProviderState(
        provider_ref=provider_ref,
        surface_id=surface_id,
        availability=availability,
        healthy=healthy,
        credential_available=credential_available,
        quota_remaining=quota_remaining,
        quota_reset_at=quota_reset_at,
        estimated_cost=estimated_cost,
        estimated_latency_ms=estimated_latency_ms,
        policy_freshness=policy_freshness,
        runtime_capabilities=runtime_capabilities,
        model_available=model_available,
        last_checked_at=last_checked_at,
        reason_codes=reason_codes,
        metadata=dict(metadata or {}),
    )
