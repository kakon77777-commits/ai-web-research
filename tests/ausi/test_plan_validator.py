from ai_web_research.core.types import ActionKind, ArtifactKind, SearchAction, VersionRef
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
from ai_web_research.planning.graph import ActionNode, EdgeKind, LoopNode, PlanEdge, SearchPlan
from ai_web_research.planning.validator import PlanValidator
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind


def spec(method_id: str, accepts, produces, capability: str) -> SearchMethodSpec:
    return SearchMethodSpec(
        method_id=method_id,
        version="1.0.0",
        availability=MethodAvailability.AVAILABLE,
        aliases=(), purpose=method_id,
        goals=frozenset({MethodGoal.DISCOVER}),
        representations=frozenset({RepresentationKind.LEXICAL}),
        directions=frozenset({SearchDirection.OUTWARD}),
        interaction_modes=frozenset({InteractionMode.ONE_SHOT}),
        evidence_effects=frozenset({EvidenceEffect.CANDIDATE}),
        input_contract=ContractSpec(accepts=frozenset(accepts)),
        output_contract=ContractSpec(produces=frozenset(produces)),
        parameter_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
        required_capabilities=frozenset({capability}),
        preconditions=(), postconditions=(), failure_modes=(),
        cost_prior={}, latency_prior={}, receipt_requirements=(), stopping_implications=(), metadata={},
    )


def setup_registries():
    methods = SearchMethodRegistry()
    methods.register(spec("method.search_a", {ArtifactKind.QUERY}, {ArtifactKind.CANDIDATE_SET}, "cap.a"))
    methods.register(spec("method.search_b", {ArtifactKind.CANDIDATE_SET}, {ArtifactKind.DOCUMENT}, "cap.b"))
    methods.register(spec("method.needs_document", {ArtifactKind.DOCUMENT}, {ArtifactKind.DOCUMENT}, "cap.b"))

    providers = ProviderRegistry()
    providers.register_provider(ProviderSpec(
        provider_id="provider.test", version="1.0.0", kind=ProviderKind.CUSTOM, display_name="Test",
        domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id="surface.test", kind=SurfaceKind.LOCAL_DATABASE, endpoint_ref=None,
            capabilities=frozenset({"cap.a", "cap.b"}), auth_profile=None, policy_profile_refs=(),
            static_limits={}, metadata={},
        ),), metadata={},
    ))
    for method_id, suffix in (("method.search_a", "a"), ("method.search_b", "b"), ("method.needs_document", "d")):
        providers.register_binding(MethodBinding(
            binding_id=f"binding.{suffix}",
            method_ref=VersionRef(method_id, "1.0.0"),
            provider_ref=VersionRef("provider.test", "1.0.0"),
            surface_id="surface.test", adapter_id=f"adapter.{suffix}", adapter_version="1",
            enabled=True, parameter_mapping={}, metadata={},
        ), methods.snapshot())
    return methods.snapshot(), providers.snapshot()


def action(action_id: str, method_id: str, binding_id: str) -> SearchAction:
    return SearchAction(
        action_id=action_id, task_id="task-1", epoch_id="epoch-1",
        method_ref=VersionRef(method_id, "1.0.0"),
        provider_ref=VersionRef("provider.test", "1.0.0"),
        surface_id="surface.test", binding_id=binding_id,
        action_kind=ActionKind.SEARCH, inputs=(), parameters={"query": "x"}, guards=(),
        expected_effects=(), created_by="test", created_at="2026-08-31T07:00:00+00:00",
    )


def test_valid_sequential_plan_passes():
    methods, providers = setup_registries()
    plan = SearchPlan(
        plan_id="plan-1", task_id="task-1", epoch_id="epoch-1",
        nodes=(ActionNode("n1", action("a1", "method.search_a", "binding.a")), ActionNode("n2", action("a2", "method.search_b", "binding.b"))),
        edges=(PlanEdge("n1", "n2", EdgeKind.NEXT, (ArtifactKind.CANDIDATE_SET,), None),),
        entry_node_ids=("n1",), metadata={},
    )
    result = PlanValidator().validate(plan, methods, providers)
    assert result.valid, result.issues


def test_unknown_binding_is_rejected():
    methods, providers = setup_registries()
    plan = SearchPlan(
        plan_id="p", task_id="task-1", epoch_id="epoch-1",
        nodes=(ActionNode("n1", action("a1", "method.search_a", "binding.missing")),),
        edges=(), entry_node_ids=("n1",), metadata={},
    )
    result = PlanValidator().validate(plan, methods, providers)
    assert "PLAN_UNKNOWN_BINDING" in {issue.code for issue in result.issues}


def test_artifact_type_mismatch_is_rejected():
    methods, providers = setup_registries()
    plan = SearchPlan(
        plan_id="p", task_id="task-1", epoch_id="epoch-1",
        nodes=(ActionNode("n1", action("a1", "method.search_a", "binding.a")), ActionNode("n2", action("a2", "method.needs_document", "binding.d"))),
        edges=(PlanEdge("n1", "n2", EdgeKind.NEXT, (ArtifactKind.CANDIDATE_SET,), None),),
        entry_node_ids=("n1",), metadata={},
    )
    result = PlanValidator().validate(plan, methods, providers)
    assert "PLAN_ARTIFACT_TYPE_MISMATCH" in {issue.code for issue in result.issues}


def test_implicit_cycle_is_rejected():
    methods, providers = setup_registries()
    nodes=(ActionNode("n1", action("a1", "method.search_a", "binding.a")), ActionNode("n2", action("a2", "method.search_b", "binding.b")))
    plan = SearchPlan(
        plan_id="p", task_id="task-1", epoch_id="epoch-1", nodes=nodes,
        edges=(
            PlanEdge("n1", "n2", EdgeKind.NEXT, (ArtifactKind.CANDIDATE_SET,), None),
            PlanEdge("n2", "n1", EdgeKind.NEXT, (), None),
        ),
        entry_node_ids=("n1",), metadata={},
    )
    result = PlanValidator().validate(plan, methods, providers)
    assert "PLAN_UNBOUNDED_CYCLE" in {issue.code for issue in result.issues}


def test_unbounded_loop_node_is_rejected():
    methods, providers = setup_registries()
    plan = SearchPlan(
        plan_id="p", task_id="task-1", epoch_id="epoch-1",
        nodes=(LoopNode("loop", "gap.open", 0),), edges=(), entry_node_ids=("loop",), metadata={},
    )
    result = PlanValidator().validate(plan, methods, providers)
    assert "PLAN_INVALID_LOOP" in {issue.code for issue in result.issues}
