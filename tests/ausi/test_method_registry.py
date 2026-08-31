import pytest

from ai_web_research.core.types import ArtifactKind, VersionRef
from ai_web_research.methods.registry import RegistryVersionConflict, SearchMethodRegistry
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


def make_spec(version: str = "1.0.0", purpose: str = "Identity search") -> SearchMethodSpec:
    return SearchMethodSpec(
        method_id="method.identity_search",
        version=version,
        availability=MethodAvailability.AVAILABLE,
        aliases=(),
        purpose=purpose,
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
        postconditions=("candidate_set_created",),
        failure_modes=(),
        cost_prior={},
        latency_prior={},
        receipt_requirements=(),
        stopping_implications=(),
        metadata={},
    )


def test_same_payload_reregistration_is_idempotent():
    registry = SearchMethodRegistry()
    spec = make_spec()
    registry.register(spec)
    registry.register(spec)
    assert registry.get(VersionRef(spec.method_id, spec.version)) == spec
    assert len(registry.list()) == 1


def test_conflicting_same_version_payload_is_rejected():
    registry = SearchMethodRegistry()
    registry.register(make_spec())
    with pytest.raises(RegistryVersionConflict):
        registry.register(make_spec(purpose="Different semantics"))


def test_latest_uses_semantic_version_order():
    registry = SearchMethodRegistry()
    registry.register(make_spec("1.2.0"))
    registry.register(make_spec("1.10.0"))
    assert registry.latest("method.identity_search").version == "1.10.0"


def test_snapshot_is_immutable_when_registry_changes():
    registry = SearchMethodRegistry()
    registry.register(make_spec("1.0.0"))
    snapshot = registry.snapshot()
    registry.register(make_spec("1.1.0"))
    assert tuple(spec.version for spec in snapshot.methods) == ("1.0.0",)
    assert tuple(spec.version for spec in registry.snapshot().methods) == ("1.0.0", "1.1.0")
