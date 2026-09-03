from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, SearchIntent, SearchState, SearchTask, VersionRef
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.corpus_builtin import build_builtin_method_corpus
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.planning.autonomous import AutonomousPlannerV1
from ai_web_research.planning.autonomous_models import (
    PlanningPolicy,
    ProposedMethodStep,
    SearchStrategyProposal,
)
from ai_web_research.planning.graph import ActionNode, BranchNode, JoinNode, LoopNode, StopNode
from ai_web_research.planning.validator import PlanValidator
from ai_web_research.providers.builtin import register_builtin_providers
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, ProviderTopology, SurfaceKind
from ai_web_research.routing.models import PolicyFreshness, ProviderAvailability, ProviderState, RoutingPolicy
from ai_web_research.routing.state import ProviderStateRegistry


def make_task(intent=SearchIntent.RESEARCH, *, budget=None):
    return SearchTask(
        task_id="task-1", raw_request="research AI search systems", intent=intent,
        domain=None, purpose="research", languages=("en",), jurisdictions=(),
        freshness={}, coverage_requirements={}, verification_requirements={}, source_preferences=(),
        risk_class=RiskClass.LOW, budget=dict(budget or {}), domain_pack=None, metadata={},
    )


def make_state(*, artifacts=None, candidates=None, gaps=(), gap_details=None, budget=None):
    return SearchState(
        task_id="task-1", epoch_id="epoch-1", planned_at="2026-09-03T08:00:00+00:00",
        active_artifacts=list(artifacts or []), candidate_refs=list(candidates or []), evidence_refs=[],
        open_gap_refs=list(gaps), completed_action_ids=[], failed_action_ids=[],
        budget_state=dict(budget or {}), coverage_state={}, metadata={"gap_details": gap_details or {}},
    )


def method_snapshot():
    registry = SearchMethodRegistry()
    register_builtin_methods(registry)
    return registry.snapshot()


def provider_snapshot(methods):
    providers = ProviderRegistry()
    register_builtin_providers(providers, methods)
    for provider_id, surface_id, binding_id, cost in (
        ("provider.search_a", "surface.search_a", "binding.lexical.search_a", 0.01),
        ("provider.search_b", "surface.search_b", "binding.lexical.search_b", 0.02),
    ):
        providers.register_provider(ProviderSpec(
            provider_id=provider_id, version="1.0.0", kind=ProviderKind.SEARCH_ENGINE,
            display_name=provider_id, domains=(), languages=(), jurisdictions=(),
            surfaces=(ProviderSurface(
                surface_id=surface_id, kind=SurfaceKind.PUBLIC_API, endpoint_ref=None,
                capabilities=frozenset({"capability.lexical"}), auth_profile=None,
                policy_profile_refs=(), static_limits={}, metadata={"cost_hint": cost},
            ),), metadata={}, topology=ProviderTopology.PROVIDER_NEUTRAL,
        ))
        providers.register_binding(MethodBinding(
            binding_id=binding_id,
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(provider_id, "1.0.0"), surface_id=surface_id,
            adapter_id=f"{provider_id}.adapter", adapter_version="1.0.0", enabled=True,
            parameter_mapping={}, metadata={},
        ), methods)
    providers.register_provider(ProviderSpec(
        provider_id="provider.counter", version="1.0.0", kind=ProviderKind.SEARCH_ENGINE,
        display_name="provider.counter", domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id="surface.counter", kind=SurfaceKind.PUBLIC_API, endpoint_ref=None,
            capabilities=frozenset({"capability.counter_search"}), auth_profile=None,
            policy_profile_refs=(), static_limits={}, metadata={},
        ),), metadata={}, topology=ProviderTopology.PROVIDER_NEUTRAL,
    ))
    providers.register_binding(MethodBinding(
        binding_id="binding.counter",
        method_ref=VersionRef("method.counter_evidence_search", "1.0.0"),
        provider_ref=VersionRef("provider.counter", "1.0.0"), surface_id="surface.counter",
        adapter_id="counter.adapter", adapter_version="1.0.0", enabled=True,
        parameter_mapping={}, metadata={},
    ), methods)
    return providers.snapshot()


def provider_states(providers):
    registry = ProviderStateRegistry()
    for provider in providers.providers:
        for surface in provider.surfaces:
            registry.observe(ProviderState(
                provider_ref=VersionRef(provider.provider_id, provider.version),
                surface_id=surface.surface_id,
                availability=ProviderAvailability.AVAILABLE,
                healthy=True,
                credential_available=True if surface.kind is SurfaceKind.AUTHENTICATED_API else None,
                quota_remaining=100.0,
                quota_reset_at=None,
                estimated_cost=(0.01 if provider.provider_id == "provider.search_a" else 0.02),
                estimated_latency_ms=100.0,
                policy_freshness=PolicyFreshness.FRESH,
                runtime_capabilities=surface.capabilities,
                model_available=True if provider.topology is ProviderTopology.MODEL_NATIVE else None,
                last_checked_at="2026-09-03T08:00:00+00:00",
            ))
    return registry.snapshot()


def route_policy(**overrides):
    values = dict(
        policy_id="routing.planner.v1",
        preferred_binding_ids=("binding.lexical.search_a", "binding.lexical.search_b"),
        preferred_provider_ids=(), preferred_topologies=(), allow_degraded=False,
        allow_unknown_state=False, require_fresh_policy_state=True,
        require_credential_for_authenticated=True, require_model_available=True,
        max_estimated_cost=None, max_estimated_latency_ms=None,
        required_runtime_capabilities=frozenset(),
    )
    values.update(overrides)
    return RoutingPolicy(**values)


def proposal(*steps, replan=False):
    return SearchStrategyProposal(
        proposal_id="proposal-1", task_id="task-1", steps=tuple(steps),
        replan_condition_ref="open_gaps_remain" if replan else None,
        max_replans=1 if replan else 0, reason_codes=("TEST_PROPOSAL",),
    )


def step(step_id, objective, *methods):
    return ProposedMethodStep(step_id, objective, tuple(methods), reason_codes=("TEST",))


def build_context():
    methods = method_snapshot()
    providers = provider_snapshot(methods)
    states = provider_states(providers)
    corpus = build_builtin_method_corpus().snapshot()
    return methods, corpus, providers, states


def test_documented_method_is_rejected_and_next_execution_ready_method_substitutes():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(), make_state(), methods, corpus, providers, states,
        route_policy(), PlanningPolicy("planning.v1"),
        proposal=proposal(step("discover", "discover_candidates", "method.exact_search", "method.lexical_search")),
    )
    assert result.decision_summary.selected_method_ids == ("method.lexical_search",)
    assert "method.exact_search" in result.decision_summary.skipped_method_ids
    assert dict(result.decision_summary.skip_reasons)["method.exact_search"] == ("LIFECYCLE_DOCUMENTED",)


def test_experimental_method_requires_explicit_planning_policy():
    methods, corpus, providers, states = build_context()
    state = make_state(artifacts=(ArtifactRef(ArtifactKind.CLAIM, "claim-1"),))
    result = AutonomousPlannerV1().plan(
        make_task(SearchIntent.FALSIFY), state, methods, corpus, providers, states,
        route_policy(), PlanningPolicy("planning.v1", allow_experimental=False),
        proposal=proposal(step("counter", "find_counter_evidence", "method.counter_evidence_search", "method.lexical_search")),
    )
    assert result.decision_summary.selected_method_ids == ("method.lexical_search",)
    assert dict(result.decision_summary.skip_reasons)["method.counter_evidence_search"] == (
        "EXPERIMENTAL_METHOD_NOT_ALLOWED",
    )


def test_provider_fallback_branch_uses_same_method_with_different_bindings():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_actions": 3, "max_provider_fallbacks": 1}), make_state(),
        methods, corpus, providers, states, route_policy(), PlanningPolicy("planning.v1"),
        proposal=proposal(step("discover", "discover_candidates", "method.lexical_search")),
    )
    action_nodes = [node for node in result.plan.nodes if isinstance(node, ActionNode)]
    lexical = [node.action for node in action_nodes if node.action.method_ref.id == "method.lexical_search"]
    assert len(lexical) == 2
    assert lexical[0].binding_id == "binding.lexical.search_a"
    assert lexical[1].binding_id == "binding.lexical.search_b"
    assert {action.method_ref for action in lexical} == {VersionRef("method.lexical_search", "1.0.0")}
    assert any(isinstance(node, BranchNode) for node in result.plan.nodes)
    assert PlanValidator().validate(result.plan, methods, providers).valid is True


def test_parallel_method_steps_converge_at_join():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_actions": 4, "max_parallel_branches": 2, "max_provider_fallbacks": 0}),
        make_state(), methods, corpus, providers, states, route_policy(), PlanningPolicy("planning.v1", enable_provider_fallback=False),
        proposal=proposal(
            step("discover", "discover_candidates", "method.lexical_search"),
            step("diverge", "diversify_queries", "method.query_divergence"),
        ),
    )
    action_nodes = [node for node in result.plan.nodes if isinstance(node, ActionNode)]
    assert {node.action.method_ref.id for node in action_nodes} == {
        "method.lexical_search", "method.query_divergence"
    }
    assert len(result.plan.entry_node_ids) == 2
    assert any(isinstance(node, JoinNode) for node in result.plan.nodes)
    assert PlanValidator().validate(result.plan, methods, providers).valid is True


def test_open_gap_proposal_compiles_bounded_replan_loop():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_loop_iterations": 3, "max_provider_fallbacks": 0}),
        make_state(gaps=("gap-1",), gap_details={"gap-1": {"type": "source_independence", "priority": 1}}),
        methods, corpus, providers, states, route_policy(), PlanningPolicy("planning.v1", enable_provider_fallback=False),
        proposal=proposal(step("discover", "discover_candidates", "method.lexical_search"), replan=True),
    )
    loops = [node for node in result.plan.nodes if isinstance(node, LoopNode)]
    assert len(loops) == 1
    assert loops[0].condition_ref == "open_gaps_remain"
    assert loops[0].max_iterations == 2
    assert any(edge.kind.value == "loop_back" for edge in result.plan.edges)
    assert PlanValidator().validate(result.plan, methods, providers).valid is True


def test_action_budget_caps_primary_and_fallback_actions():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_actions": 1, "max_provider_fallbacks": 1}), make_state(),
        methods, corpus, providers, states, route_policy(), PlanningPolicy("planning.v1"),
        proposal=proposal(
            step("discover", "discover_candidates", "method.lexical_search"),
            step("diverge", "diversify_queries", "method.query_divergence"),
        ),
    )
    action_nodes = [node for node in result.plan.nodes if isinstance(node, ActionNode)]
    assert len(action_nodes) == 1
    assert action_nodes[0].action.method_ref.id == "method.lexical_search"


def test_no_execution_ready_method_returns_explicit_stop_plan():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(), make_state(), methods, corpus, providers, states,
        route_policy(), PlanningPolicy("planning.v1"),
        proposal=proposal(step("exact", "exact_lookup", "method.exact_search")),
    )
    assert len(result.plan.nodes) == 1
    assert isinstance(result.plan.nodes[0], StopNode)
    assert result.plan.nodes[0].stop.reason == "NO_EXECUTION_READY_METHOD"
    assert result.decision_summary.selected_method_ids == ()


def test_experimental_method_can_compile_when_explicitly_allowed_and_bound():
    methods, corpus, providers, states = build_context()
    state = make_state(artifacts=(ArtifactRef(ArtifactKind.CLAIM, "claim-1"),))
    result = AutonomousPlannerV1().plan(
        make_task(SearchIntent.FALSIFY, budget={"max_provider_fallbacks": 0}),
        state, methods, corpus, providers, states,
        route_policy(), PlanningPolicy("planning.v1", allow_experimental=True, enable_provider_fallback=False),
        proposal=proposal(step("counter", "find_counter_evidence", "method.counter_evidence_search")),
    )
    assert result.decision_summary.selected_method_ids == ("method.counter_evidence_search",)
    action = next(node.action for node in result.plan.nodes if isinstance(node, ActionNode))
    assert action.binding_id == "binding.counter"
    assert PlanValidator().validate(result.plan, methods, providers).valid is True


def test_query_divergence_can_be_disabled_by_planning_policy():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_actions": 4, "max_parallel_branches": 2, "max_provider_fallbacks": 0}),
        make_state(), methods, corpus, providers, states, route_policy(),
        PlanningPolicy("planning.v1", enable_query_divergence=False, enable_provider_fallback=False),
        proposal=proposal(
            step("discover", "discover_candidates", "method.lexical_search"),
            step("diverge", "diversify_queries", "method.query_divergence"),
        ),
    )
    assert result.decision_summary.selected_method_ids == ("method.lexical_search",)
    assert dict(result.decision_summary.skip_reasons)["method.query_divergence"] == (
        "QUERY_DIVERGENCE_DISABLED",
    )


def test_provider_fallback_limit_is_global_across_plan():
    methods, corpus, providers, states = build_context()
    result = AutonomousPlannerV1().plan(
        make_task(budget={"max_actions": 5, "max_parallel_branches": 2, "max_provider_fallbacks": 1}),
        make_state(), methods, corpus, providers, states, route_policy(), PlanningPolicy("planning.v1"),
        proposal=proposal(
            step("discover-1", "discover_candidates", "method.lexical_search"),
            step("discover-2", "discover_candidates_second", "method.lexical_search"),
        ),
    )
    lexical_actions = [
        node.action for node in result.plan.nodes
        if isinstance(node, ActionNode) and node.action.method_ref.id == "method.lexical_search"
    ]
    assert len(lexical_actions) == 3
    assert sum(1 for node in result.plan.nodes if isinstance(node, BranchNode)) == 1
