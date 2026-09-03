import pytest

from ai_web_research.core.types import VersionRef
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import (
    MethodBinding,
    ProviderKind,
    ProviderSpec,
    ProviderSurface,
    ProviderTopology,
    SurfaceKind,
)
from ai_web_research.routing.models import (
    PolicyFreshness,
    ProviderAvailability,
    ProviderState,
    RoutingPolicy,
)
from ai_web_research.routing.selector import BindingSelector, NoEligibleBinding
from ai_web_research.routing.state import ProviderStateRegistry

METHOD = VersionRef("method.lexical_search", "1.0.0")


def build_provider_registry():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    rows = (
        ("provider.vertex", "surface.vertex", "binding.vertex", ProviderTopology.MODEL_NATIVE),
        ("provider.gemini", "surface.gemini", "binding.gemini", ProviderTopology.MODEL_NATIVE),
        ("provider.grok", "surface.grok.web", "binding.grok", ProviderTopology.MODEL_NATIVE),
        ("provider.brave", "surface.brave", "binding.brave", ProviderTopology.PROVIDER_NEUTRAL),
    )
    for provider_id, surface_id, binding_id, topology in rows:
        providers.register_provider(
            ProviderSpec(
                provider_id=provider_id,
                version="1.0.0",
                kind=ProviderKind.SEARCH_ENGINE,
                display_name=provider_id,
                domains=(),
                languages=(),
                jurisdictions=(),
                surfaces=(
                    ProviderSurface(
                        surface_id=surface_id,
                        kind=SurfaceKind.AUTHENTICATED_API,
                        endpoint_ref=None,
                        capabilities=frozenset({"capability.lexical"}),
                        auth_profile=f"{provider_id}.credential",
                        policy_profile_refs=(),
                        static_limits={},
                        metadata={},
                    ),
                ),
                metadata={},
                topology=topology,
            )
        )
        providers.register_binding(
            MethodBinding(
                binding_id=binding_id,
                method_ref=METHOD,
                provider_ref=VersionRef(provider_id, "1.0.0"),
                surface_id=surface_id,
                adapter_id=f"{provider_id}.adapter",
                adapter_version="1.0.0",
                enabled=True,
                parameter_mapping={},
                metadata={},
            ),
            methods.snapshot(),
        )
    return providers.snapshot()


def state(provider_id, surface_id, **overrides):
    values = dict(
        provider_ref=VersionRef(provider_id, "1.0.0"),
        surface_id=surface_id,
        availability=ProviderAvailability.AVAILABLE,
        healthy=True,
        credential_available=True,
        quota_remaining=100.0,
        quota_reset_at=None,
        estimated_cost=0.01,
        estimated_latency_ms=500.0,
        policy_freshness=PolicyFreshness.FRESH,
        runtime_capabilities=frozenset({"capability.lexical"}),
        model_available=True,
        last_checked_at="2026-09-03T06:00:00+00:00",
        reason_codes=(),
        metadata={},
    )
    values.update(overrides)
    return ProviderState(**values)


def states(*items):
    registry = ProviderStateRegistry()
    for item in items:
        registry.observe(item)
    return registry.snapshot()


def preferred_policy(**overrides):
    values = dict(
        policy_id="routing.default",
        preferred_binding_ids=("binding.vertex", "binding.gemini", "binding.grok", "binding.brave"),
        preferred_provider_ids=(),
        preferred_topologies=(),
        allow_degraded=False,
        allow_unknown_state=False,
        require_fresh_policy_state=True,
        require_credential_for_authenticated=True,
        require_model_available=True,
        max_estimated_cost=None,
        max_estimated_latency_ms=None,
        required_runtime_capabilities=frozenset({"capability.lexical"}),
    )
    values.update(overrides)
    return RoutingPolicy(**values)


def full_states(**vertex_overrides):
    return states(
        state("provider.vertex", "surface.vertex", **vertex_overrides),
        state("provider.gemini", "surface.gemini", estimated_cost=0.02),
        state("provider.grok", "surface.grok.web", estimated_cost=0.03),
        state("provider.brave", "surface.brave", estimated_cost=0.04),
    )


def test_preferred_binding_wins_when_all_are_eligible():
    decision = BindingSelector().select(METHOD, build_provider_registry(), full_states(), preferred_policy())
    assert decision.selected_binding_id == "binding.vertex"
    assert decision.selected_provider_ref.id == "provider.vertex"
    assert decision.method_ref == METHOD


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"availability": ProviderAvailability.UNAVAILABLE}, "PROVIDER_UNAVAILABLE"),
        ({"availability": ProviderAvailability.DEGRADED}, "PROVIDER_DEGRADED"),
        ({"healthy": False}, "PROVIDER_UNHEALTHY"),
        ({"credential_available": False}, "CREDENTIAL_UNAVAILABLE"),
        ({"credential_available": None}, "CREDENTIAL_UNKNOWN"),
        ({"model_available": False}, "MODEL_UNAVAILABLE"),
        ({"quota_remaining": 0.0}, "QUOTA_EXHAUSTED"),
        ({"policy_freshness": PolicyFreshness.STALE}, "POLICY_STATE_STALE"),
        ({"runtime_capabilities": frozenset()}, "RUNTIME_CAPABILITY_MISSING"),
    ],
)
def test_hard_state_rejection_falls_back_to_next_binding(overrides, reason):
    decision = BindingSelector().select(METHOD, build_provider_registry(), full_states(**overrides), preferred_policy())
    assert decision.selected_binding_id == "binding.gemini"
    vertex = next(c for c in decision.candidates if c.binding_id == "binding.vertex")
    assert vertex.eligible is False
    assert reason in vertex.reason_codes


def test_degraded_provider_can_be_explicitly_allowed():
    decision = BindingSelector().select(
        METHOD,
        build_provider_registry(),
        full_states(availability=ProviderAvailability.DEGRADED),
        preferred_policy(allow_degraded=True),
    )
    assert decision.selected_binding_id == "binding.vertex"


def test_cost_and_latency_limits_reject_candidates():
    registry = build_provider_registry()
    snapshot = states(
        state("provider.vertex", "surface.vertex", estimated_cost=5.0),
        state("provider.gemini", "surface.gemini", estimated_latency_ms=5000.0),
        state("provider.grok", "surface.grok.web", estimated_cost=0.03, estimated_latency_ms=700.0),
        state("provider.brave", "surface.brave", estimated_cost=0.04),
    )
    decision = BindingSelector().select(
        METHOD,
        registry,
        snapshot,
        preferred_policy(max_estimated_cost=1.0, max_estimated_latency_ms=1000.0),
    )
    assert decision.selected_binding_id == "binding.grok"
    assert "COST_LIMIT_EXCEEDED" in next(c for c in decision.candidates if c.binding_id == "binding.vertex").reason_codes
    assert "LATENCY_LIMIT_EXCEEDED" in next(c for c in decision.candidates if c.binding_id == "binding.gemini").reason_codes


def test_missing_state_is_ineligible_by_default():
    decision = BindingSelector().select(
        METHOD,
        build_provider_registry(),
        states(state("provider.brave", "surface.brave")),
        preferred_policy(),
    )
    assert decision.selected_binding_id == "binding.brave"
    vertex = next(c for c in decision.candidates if c.binding_id == "binding.vertex")
    assert "MISSING_PROVIDER_STATE" in vertex.reason_codes


def test_no_eligible_binding_raises_with_auditable_decision():
    with pytest.raises(NoEligibleBinding) as excinfo:
        BindingSelector().select(METHOD, build_provider_registry(), states(), preferred_policy())
    decision = excinfo.value.decision
    assert decision.selected_binding_id is None
    assert len(decision.candidates) == 4
    assert all("MISSING_PROVIDER_STATE" in c.reason_codes for c in decision.candidates)


def test_without_explicit_preferences_fallback_is_deterministic_cost_then_latency_then_ids():
    registry = build_provider_registry()
    snapshot = states(
        state("provider.vertex", "surface.vertex", estimated_cost=0.03, estimated_latency_ms=100.0),
        state("provider.gemini", "surface.gemini", estimated_cost=0.01, estimated_latency_ms=900.0),
        state("provider.grok", "surface.grok.web", estimated_cost=0.01, estimated_latency_ms=500.0),
        state("provider.brave", "surface.brave", estimated_cost=0.02, estimated_latency_ms=50.0),
    )
    decision = BindingSelector().select(
        METHOD,
        registry,
        snapshot,
        preferred_policy(preferred_binding_ids=()),
    )
    assert decision.selected_binding_id == "binding.grok"


def test_provider_preference_can_override_cost_when_binding_preference_is_absent():
    decision = BindingSelector().select(
        METHOD,
        build_provider_registry(),
        full_states(),
        preferred_policy(
            preferred_binding_ids=(),
            preferred_provider_ids=("provider.brave",),
        ),
    )
    assert decision.selected_binding_id == "binding.brave"
    assert decision.reason_codes == ("SELECTED_BY_PROVIDER_PREFERENCE",)


def test_topology_preference_can_select_provider_neutral_channel():
    decision = BindingSelector().select(
        METHOD,
        build_provider_registry(),
        full_states(),
        preferred_policy(
            preferred_binding_ids=(),
            preferred_provider_ids=(),
            preferred_topologies=(ProviderTopology.PROVIDER_NEUTRAL, ProviderTopology.MODEL_NATIVE),
        ),
    )
    assert decision.selected_binding_id == "binding.brave"
    assert decision.reason_codes == ("SELECTED_BY_TOPOLOGY_PREFERENCE",)
