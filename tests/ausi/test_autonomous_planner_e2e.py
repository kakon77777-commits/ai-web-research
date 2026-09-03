from pathlib import Path

from ai_web_research.core.types import RiskClass, SearchIntent, SearchState, SearchTask, VersionRef
from ai_web_research.experience.receipt import SearchReceiptRecorder, SearchReceiptStatus
from ai_web_research.experience.sqlite import SearchReceiptStore
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.corpus_builtin import build_builtin_method_corpus
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.planning.autonomous import AutonomousPlannerV1
from ai_web_research.planning.autonomous_models import PlanningPolicy
from ai_web_research.planning.graph import ActionNode, BranchNode, LoopNode
from ai_web_research.planning.receipt import planning_receipt_metadata
from ai_web_research.planning.validator import PlanValidator
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, ProviderTopology, SurfaceKind
from ai_web_research.routing.models import PolicyFreshness, ProviderAvailability, ProviderState, RoutingPolicy
from ai_web_research.routing.state import ProviderStateRegistry


def task():
    return SearchTask(
        task_id="task-falsify", raw_request="find evidence against the current claim",
        intent=SearchIntent.FALSIFY, domain=None, purpose="research", languages=("en",), jurisdictions=(),
        freshness={}, coverage_requirements={}, verification_requirements={}, source_preferences=(),
        risk_class=RiskClass.LOW,
        budget={"max_actions": 3, "max_parallel_branches": 2, "max_loop_iterations": 2, "max_provider_fallbacks": 1},
        domain_pack=None, metadata={},
    )


def state():
    return SearchState(
        task_id="task-falsify", epoch_id="epoch-falsify", planned_at="2026-09-03T08:30:00+00:00",
        active_artifacts=[], candidate_refs=[], evidence_refs=[], open_gap_refs=["gap-counter"],
        completed_action_ids=[], failed_action_ids=[], budget_state={}, coverage_state={},
        metadata={"gap_details": {"gap-counter": {"type": "counter_evidence", "priority": 100}}},
    )


def context():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    method_snapshot = methods.snapshot()
    providers = ProviderRegistry()
    for index in (1, 2):
        provider_id = f"provider.neutral_{index}"
        surface_id = f"surface.neutral_{index}"
        binding_id = f"binding.lexical.neutral_{index}"
        providers.register_provider(ProviderSpec(
            provider_id=provider_id, version="1.0.0", kind=ProviderKind.SEARCH_ENGINE,
            display_name=provider_id, domains=(), languages=(), jurisdictions=(),
            surfaces=(ProviderSurface(
                surface_id=surface_id, kind=SurfaceKind.PUBLIC_API, endpoint_ref=None,
                capabilities=frozenset({"capability.lexical"}), auth_profile=None,
                policy_profile_refs=(), static_limits={}, metadata={},
            ),), metadata={}, topology=ProviderTopology.PROVIDER_NEUTRAL,
        ))
        providers.register_binding(MethodBinding(
            binding_id=binding_id, method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(provider_id, "1.0.0"), surface_id=surface_id,
            adapter_id=f"neutral.{index}", adapter_version="1.0.0", enabled=True,
            parameter_mapping={}, metadata={},
        ), method_snapshot)
    provider_snapshot = providers.snapshot()

    states = ProviderStateRegistry()
    for provider in provider_snapshot.providers:
        surface = provider.surfaces[0]
        states.observe(ProviderState(
            provider_ref=VersionRef(provider.provider_id, provider.version), surface_id=surface.surface_id,
            availability=ProviderAvailability.AVAILABLE, healthy=True, credential_available=None,
            quota_remaining=100.0, quota_reset_at=None,
            estimated_cost=0.01 if provider.provider_id.endswith("1") else 0.02,
            estimated_latency_ms=100.0 if provider.provider_id.endswith("1") else 150.0,
            policy_freshness=PolicyFreshness.FRESH, runtime_capabilities=surface.capabilities,
            model_available=None, last_checked_at="2026-09-03T08:30:00+00:00",
        ))
    return method_snapshot, build_builtin_method_corpus().snapshot(), provider_snapshot, states.snapshot()


def routing_policy():
    return RoutingPolicy(
        policy_id="routing.e2e",
        preferred_binding_ids=("binding.lexical.neutral_1", "binding.lexical.neutral_2"),
        preferred_provider_ids=(), preferred_topologies=(), allow_degraded=False,
        allow_unknown_state=False, require_fresh_policy_state=True,
        require_credential_for_authenticated=True, require_model_available=True,
        max_estimated_cost=None, max_estimated_latency_ms=None,
        required_runtime_capabilities=frozenset(),
    )


def walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key).lower()
            yield from walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_keys(nested)


def test_falsify_gap_plans_method_substitution_provider_fallback_loop_and_safe_receipt(tmp_path: Path):
    methods, corpus, providers, provider_states = context()
    result = AutonomousPlannerV1().plan(
        task(), state(), methods, corpus, providers, provider_states,
        routing_policy(), PlanningPolicy("planning.e2e", allow_experimental=False),
    )

    assert all(
        all(not method_id.startswith("provider.") for method_id in step.candidate_method_ids)
        for step in result.proposal.steps
    )
    assert result.proposal.steps[0].candidate_method_ids == (
        "method.counter_evidence_search", "method.lexical_search"
    )
    assert result.decision_summary.selected_method_ids == ("method.lexical_search",)
    assert dict(result.decision_summary.skip_reasons)["method.counter_evidence_search"] == (
        "EXPERIMENTAL_METHOD_NOT_ALLOWED",
    )

    lexical_actions = [
        node.action for node in result.plan.nodes
        if isinstance(node, ActionNode) and node.action.method_ref.id == "method.lexical_search"
    ]
    assert [action.binding_id for action in lexical_actions] == [
        "binding.lexical.neutral_1", "binding.lexical.neutral_2"
    ]
    assert any(isinstance(node, BranchNode) for node in result.plan.nodes)
    loops = [node for node in result.plan.nodes if isinstance(node, LoopNode)]
    assert len(loops) == 1 and loops[0].max_iterations == 2
    assert PlanValidator().validate(result.plan, methods, providers).valid is True

    metadata = planning_receipt_metadata(result)
    assert metadata["selected_method_ids"] == ["method.lexical_search"]
    assert metadata["gap_refs"] == ["gap-counter"]
    forbidden = {
        "api_key", "access_token", "refresh_token", "client_secret", "private_key", "password",
        "credential_value", "chain_of_thought", "private_reasoning", "authorization", "policy_decision",
    }
    assert not set(walk_keys(metadata)).intersection(forbidden)

    store = SearchReceiptStore(tmp_path / "receipt.sqlite")
    try:
        receipt = SearchReceiptRecorder(store).finalize(
            receipt_id="receipt-e2e", task_id="task-falsify", epoch_id="epoch-falsify",
            registry_snapshot_id=providers.snapshot_id,
            planner_id=AutonomousPlannerV1.planner_id,
            planner_version=AutonomousPlannerV1.planner_version,
            stop_reason="EPOCH_COMPLETE_OR_REPLAN", status=SearchReceiptStatus.PARTIAL,
            created_at="2026-09-03T08:30:00+00:00",
            metadata={"planning": metadata},
        )
        loaded = store.get_search_receipt(receipt.receipt_id)
        assert loaded.metadata["planning"]["proposal_id"] == result.proposal.proposal_id
        assert loaded.metadata["planning"]["selected_method_ids"] == ["method.lexical_search"]
    finally:
        store.close()
