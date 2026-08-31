from dataclasses import replace
import pytest

from ai_web_research.core.types import ArtifactKind, VersionRef
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.methods.spec import (
    ContractSpec,
    EvidenceEffect,
    InteractionMode,
    MethodAvailability,
    MethodGoal,
    RepresentationKind,
    SearchDirection,
    SearchMethodSpec,
)
from ai_web_research.providers.registry import BindingValidationError, ProviderRegistry
from ai_web_research.providers.spec import (
    MethodBinding,
    ProviderKind,
    ProviderSpec,
    ProviderSurface,
    SurfaceKind,
)


def method_spec() -> SearchMethodSpec:
    return SearchMethodSpec(
        method_id="method.identity_search",
        version="1.0.0",
        availability=MethodAvailability.AVAILABLE,
        aliases=(),
        purpose="Resolve identities in a local corpus",
        goals=frozenset({MethodGoal.LOCATE}),
        representations=frozenset({RepresentationKind.LEXICAL}),
        directions=frozenset({SearchDirection.INWARD}),
        interaction_modes=frozenset({InteractionMode.ONE_SHOT}),
        evidence_effects=frozenset({EvidenceEffect.CANDIDATE}),
        input_contract=ContractSpec(accepts=frozenset({ArtifactKind.QUERY})),
        output_contract=ContractSpec(produces=frozenset({ArtifactKind.CANDIDATE_SET})),
        parameter_schema={"type": "object"},
        required_capabilities=frozenset({"capability.lexical", "capability.identity_fold"}),
        preconditions=(),
        postconditions=(),
        failure_modes=(),
        cost_prior={},
        latency_prior={},
        receipt_requirements=(),
        stopping_implications=(),
        metadata={},
    )


def provider_spec(capabilities=frozenset({"capability.lexical", "capability.identity_fold"})) -> ProviderSpec:
    return ProviderSpec(
        provider_id="provider.local_corpus",
        version="1.0.0",
        kind=ProviderKind.LOCAL_CORPUS,
        display_name="Local corpus",
        domains=(),
        languages=(),
        jurisdictions=(),
        surfaces=(
            ProviderSurface(
                surface_id="surface.local.sqlite",
                kind=SurfaceKind.LOCAL_DATABASE,
                endpoint_ref=None,
                capabilities=capabilities,
                auth_profile=None,
                policy_profile_refs=(),
                static_limits={},
                metadata={},
            ),
        ),
        metadata={},
    )


def binding(surface_id="surface.local.sqlite") -> MethodBinding:
    return MethodBinding(
        binding_id="binding.identity_search.local_corpus.v1",
        method_ref=VersionRef("method.identity_search", "1.0.0"),
        provider_ref=VersionRef("provider.local_corpus", "1.0.0"),
        surface_id=surface_id,
        adapter_id="legacy.identity_search",
        adapter_version="1",
        enabled=True,
        parameter_mapping={},
        metadata={},
    )


def registries():
    methods = SearchMethodRegistry()
    methods.register(method_spec())
    providers = ProviderRegistry()
    providers.register_provider(provider_spec())
    return methods, providers


def test_capability_match_is_not_executable_without_binding():
    methods, providers = registries()
    assert providers.bindings_for_method(VersionRef("method.identity_search", "1.0.0")) == ()


def test_valid_binding_registers_and_snapshot_is_immutable():
    methods, providers = registries()
    providers.register_binding(binding(), methods.snapshot())
    snapshot = providers.snapshot()
    assert len(snapshot.bindings) == 1
    providers.register_provider(
        ProviderSpec(
            provider_id="provider.second",
            version="1.0.0",
            kind=ProviderKind.CUSTOM,
            display_name="Second",
            domains=(), languages=(), jurisdictions=(), surfaces=(), metadata={},
        )
    )
    assert len(snapshot.providers) == 1
    assert len(providers.snapshot().providers) == 2


def test_binding_rejects_missing_surface():
    methods, providers = registries()
    with pytest.raises(BindingValidationError, match="surface"):
        providers.register_binding(binding("surface.missing"), methods.snapshot())


def test_binding_rejects_missing_required_capability():
    methods = SearchMethodRegistry()
    methods.register(method_spec())
    providers = ProviderRegistry()
    providers.register_provider(provider_spec(frozenset({"capability.lexical"})))
    with pytest.raises(BindingValidationError, match="capabil"):
        providers.register_binding(binding(), methods.snapshot())


def test_snapshot_hash_changes_when_provider_payload_changes():
    left = ProviderRegistry()
    right = ProviderRegistry()
    base = provider_spec()
    left.register_provider(base)
    right.register_provider(replace(base, display_name="Changed provider semantics"))
    assert left.snapshot().snapshot_id != right.snapshot().snapshot_id
