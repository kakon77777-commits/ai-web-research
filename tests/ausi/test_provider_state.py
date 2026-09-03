import pytest

from ai_web_research.core.types import VersionRef
from ai_web_research.routing.models import (
    PolicyFreshness,
    ProviderAvailability,
    ProviderState,
)
from ai_web_research.routing.state import (
    ProviderStateRegistry,
    ProviderStateSemanticConflict,
    StaleProviderStateObservation,
)


def make_state(**overrides):
    values = dict(
        provider_ref=VersionRef("provider.grok", "1.0.0"),
        surface_id="surface.grok.web_search",
        availability=ProviderAvailability.AVAILABLE,
        healthy=True,
        credential_available=True,
        quota_remaining=100.0,
        quota_reset_at="2026-09-03T16:00:00+00:00",
        estimated_cost=0.01,
        estimated_latency_ms=600.0,
        policy_freshness=PolicyFreshness.FRESH,
        runtime_capabilities=frozenset({"capability.lexical"}),
        model_available=True,
        last_checked_at="2026-09-03T06:00:00+00:00",
        reason_codes=(),
        metadata={"source": "fixture"},
    )
    values.update(overrides)
    return ProviderState(**values)


def test_provider_state_snapshot_exact_lookup_and_content_hash():
    registry = ProviderStateRegistry()
    state = make_state()
    registry.observe(state)
    snapshot = registry.snapshot()

    assert snapshot.get(state.provider_ref, state.surface_id) == state
    assert len(snapshot.snapshot_id) == 64
    assert snapshot.states == (state,)

    other = ProviderStateRegistry()
    other.observe(make_state(estimated_cost=0.02))
    assert other.snapshot().snapshot_id != snapshot.snapshot_id


def test_newer_observation_replaces_older_state():
    registry = ProviderStateRegistry()
    registry.observe(make_state(estimated_cost=0.03, last_checked_at="2026-09-03T06:00:00+00:00"))
    registry.observe(make_state(estimated_cost=0.01, last_checked_at="2026-09-03T06:05:00+00:00"))
    state = registry.snapshot().get(VersionRef("provider.grok", "1.0.0"), "surface.grok.web_search")
    assert state.estimated_cost == 0.01
    assert state.last_checked_at == "2026-09-03T06:05:00+00:00"


def test_older_observation_cannot_replace_newer_state():
    registry = ProviderStateRegistry()
    registry.observe(make_state(last_checked_at="2026-09-03T06:05:00+00:00"))
    with pytest.raises(StaleProviderStateObservation):
        registry.observe(make_state(last_checked_at="2026-09-03T06:00:00+00:00"))


def test_same_timestamp_conflicting_state_fails_closed_but_identical_is_idempotent():
    registry = ProviderStateRegistry()
    state = make_state()
    registry.observe(state)
    registry.observe(state)
    with pytest.raises(ProviderStateSemanticConflict):
        registry.observe(make_state(healthy=False))


def test_snapshot_lookup_is_provider_version_and_surface_specific():
    registry = ProviderStateRegistry()
    registry.observe(make_state())
    with pytest.raises(KeyError):
        registry.snapshot().get(VersionRef("provider.grok", "2.0.0"), "surface.grok.web_search")
    with pytest.raises(KeyError):
        registry.snapshot().get(VersionRef("provider.grok", "1.0.0"), "surface.grok.x_search")


def test_credential_presence_helper_returns_only_boolean_and_never_retains_secret():
    from ai_web_research.routing.deployment import credential_available_from_services

    services = {
        "xai_api_key": "SECRET_XAI_SENTINEL",
        "gemini_api_key": "SECRET_GEMINI_SENTINEL",
        "blank": "   ",
    }
    assert credential_available_from_services("xai_api_key", services) is True
    assert credential_available_from_services("gemini_api_key", services) is True
    assert credential_available_from_services("blank", services) is False
    assert credential_available_from_services("missing", services) is False


def test_observe_surface_state_never_copies_credential_value():
    from ai_web_research.routing.deployment import observe_surface_state

    services = {"xai_api_key": "SECRET_XAI_SENTINEL"}
    observed = observe_surface_state(
        provider_ref=VersionRef("provider.grok", "1.0.0"),
        surface_id="surface.grok.web_search",
        last_checked_at="2026-09-03T06:10:00+00:00",
        credential_service_key="xai_api_key",
        services=services,
        availability=ProviderAvailability.AVAILABLE,
        healthy=True,
        quota_remaining=25.0,
        estimated_cost=0.02,
        estimated_latency_ms=750.0,
        policy_freshness=PolicyFreshness.FRESH,
        runtime_capabilities=frozenset({"capability.lexical"}),
        model_available=True,
        reason_codes=("LIVE_PROBE_OK",),
        metadata={"probe": "fixture"},
    )
    assert observed.credential_available is True
    assert "SECRET_XAI_SENTINEL" not in repr(observed)
    assert "xai_api_key" not in repr(observed)


def test_provider_state_rejects_obvious_secret_metadata_keys():
    with pytest.raises(ValueError, match="sensitive metadata key"):
        make_state(metadata={"api_key": "SECRET_XAI_SENTINEL"})
    with pytest.raises(ValueError, match="sensitive metadata key"):
        make_state(metadata={"refresh_token": "SECRET_REFRESH_SENTINEL"})
