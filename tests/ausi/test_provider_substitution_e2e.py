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
PREFERENCE = (
    "binding.lexical_search.gemini_google_vertex.v1",
    "binding.lexical_search.gemini_google.v1",
    "binding.lexical_search.grok_web.v1",
    "binding.lexical_search.brave_search.v1",
)

ROWS = (
    (
        "provider.gemini_google_vertex",
        "surface.gemini.google_search_vertex",
        PREFERENCE[0],
        ProviderTopology.MODEL_NATIVE,
    ),
    (
        "provider.gemini_google",
        "surface.gemini.google_search",
        PREFERENCE[1],
        ProviderTopology.MODEL_NATIVE,
    ),
    (
        "provider.grok",
        "surface.grok.web_search",
        PREFERENCE[2],
        ProviderTopology.MODEL_NATIVE,
    ),
    (
        "provider.brave_search",
        "surface.brave_search.web",
        PREFERENCE[3],
        ProviderTopology.PROVIDER_NEUTRAL,
    ),
)


def providers_snapshot():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    for provider_id, surface_id, binding_id, topology in ROWS:
        providers.register_provider(
            ProviderSpec(
                provider_id=provider_id,
                version="1.0.0",
                kind=ProviderKind.SEARCH_ENGINE,
                display_name=provider_id,
                domains=(),
                languages=(),
                jurisdictions=(),
                surfaces=(ProviderSurface(
                    surface_id=surface_id,
                    kind=SurfaceKind.AUTHENTICATED_API,
                    endpoint_ref=None,
                    capabilities=frozenset({"capability.lexical"}),
                    auth_profile=f"auth.{provider_id}",
                    policy_profile_refs=(),
                    static_limits={},
                    metadata={},
                ),),
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
                adapter_id=f"adapter.{provider_id}",
                adapter_version="1.0.0",
                enabled=True,
                parameter_mapping={},
                metadata={},
            ),
            methods.snapshot(),
        )
    return providers.snapshot()


def make_state(provider_id, surface_id, **overrides):
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


def snapshot(overrides=None):
    overrides = overrides or {}
    registry = ProviderStateRegistry()
    for provider_id, surface_id, _, _ in ROWS:
        registry.observe(make_state(provider_id, surface_id, **overrides.get(provider_id, {})))
    return registry.snapshot()


def policy():
    return RoutingPolicy(
        policy_id="routing.omphalos.default-v0.2",
        preferred_binding_ids=PREFERENCE,
        required_runtime_capabilities=frozenset({"capability.lexical"}),
    )


def candidate(decision, binding_id):
    return next(item for item in decision.candidates if item.binding_id == binding_id)


def test_same_method_substitutes_vertex_to_ai_studio_to_grok_to_brave():
    selector = BindingSelector()
    providers = providers_snapshot()

    vertex = selector.select(METHOD, providers, snapshot(), policy())
    assert vertex.method_ref == METHOD
    assert vertex.selected_binding_id == PREFERENCE[0]

    ai_studio = selector.select(
        METHOD,
        providers,
        snapshot({"provider.gemini_google_vertex": {"quota_remaining": 0.0}}),
        policy(),
    )
    assert ai_studio.method_ref == METHOD
    assert ai_studio.selected_binding_id == PREFERENCE[1]
    assert "QUOTA_EXHAUSTED" in candidate(ai_studio, PREFERENCE[0]).reason_codes

    grok = selector.select(
        METHOD,
        providers,
        snapshot({
            "provider.gemini_google_vertex": {"quota_remaining": 0.0},
            "provider.gemini_google": {"credential_available": False},
        }),
        policy(),
    )
    assert grok.method_ref == METHOD
    assert grok.selected_binding_id == PREFERENCE[2]
    assert "CREDENTIAL_UNAVAILABLE" in candidate(grok, PREFERENCE[1]).reason_codes

    brave = selector.select(
        METHOD,
        providers,
        snapshot({
            "provider.gemini_google_vertex": {"quota_remaining": 0.0},
            "provider.gemini_google": {"credential_available": False},
            "provider.grok": {"availability": ProviderAvailability.UNAVAILABLE},
        }),
        policy(),
    )
    assert brave.method_ref == METHOD
    assert brave.selected_binding_id == PREFERENCE[3]
    assert "PROVIDER_UNAVAILABLE" in candidate(brave, PREFERENCE[2]).reason_codes

    with pytest.raises(NoEligibleBinding) as excinfo:
        selector.select(
            METHOD,
            providers,
            snapshot({
                "provider.gemini_google_vertex": {"quota_remaining": 0.0},
                "provider.gemini_google": {"credential_available": False},
                "provider.grok": {"availability": ProviderAvailability.UNAVAILABLE},
                "provider.brave_search": {"availability": ProviderAvailability.UNAVAILABLE},
            }),
            policy(),
        )
    final = excinfo.value.decision
    assert final.method_ref == METHOD
    assert final.selected_binding_id is None
    assert final.reason_codes == ("NO_ELIGIBLE_BINDING",)
    assert "PROVIDER_UNAVAILABLE" in candidate(final, PREFERENCE[3]).reason_codes
