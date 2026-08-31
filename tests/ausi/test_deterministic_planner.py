import asyncio

import pytest

from ai_web_research.core.types import RiskClass, SearchIntent, SearchState, SearchTask, VersionRef
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.methods.spec import MethodAvailability
from ai_web_research.planning.graph import ActionNode
from ai_web_research.planning.planner import DeterministicPlanner, PlanningError
from ai_web_research.planning.validator import PlanValidator
from ai_web_research.providers.builtin import register_builtin_providers
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import SurfaceKind


def task(intent: SearchIntent) -> SearchTask:
    return SearchTask(
        task_id="task-identity",
        raw_request="find Alpha Engine",
        intent=intent,
        domain=None,
        purpose=None,
        languages=("en",),
        jurisdictions=(),
        freshness={},
        coverage_requirements={},
        verification_requirements={},
        source_preferences=(),
        risk_class=RiskClass.LOW,
        budget={"max_actions": 1},
        domain_pack=None,
        metadata={},
    )


def state() -> SearchState:
    return SearchState(
        task_id="task-identity",
        epoch_id="epoch-1",
        active_artifacts=[], candidate_refs=[], evidence_refs=[], open_gap_refs=[],
        completed_action_ids=[], failed_action_ids=[], budget_state={"remaining_actions": 1},
        coverage_state={}, metadata={}, planned_at="2026-08-31T07:00:00+00:00",
    )


def registries():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_builtin_providers(providers, methods.snapshot())
    return methods, providers


def test_builtin_method_availability_matches_current_repository_capabilities():
    methods, _ = registries()
    expected = {
        "method.query_divergence": MethodAvailability.AVAILABLE,
        "method.identity_search": MethodAvailability.AVAILABLE,
        "method.lexical_search": MethodAvailability.AVAILABLE,
        "method.crawl_discovery": MethodAvailability.AVAILABLE,
        "method.fetch_document": MethodAvailability.AVAILABLE,
        "method.llm_recall": MethodAvailability.AVAILABLE,
        "method.extract_candidate_evidence": MethodAvailability.AVAILABLE,
        "method.semantic_search": MethodAvailability.UNAVAILABLE,
        "method.forward_citation": MethodAvailability.UNAVAILABLE,
        "method.backward_citation": MethodAvailability.UNAVAILABLE,
        "method.temporal_version_search": MethodAvailability.UNAVAILABLE,
        "method.counter_evidence_search": MethodAvailability.PARTIAL,
    }
    actual = {spec.method_id: spec.availability for spec in methods.list()}
    assert actual == expected
    identity = methods.latest("method.identity_search")
    assert identity.required_capabilities == frozenset({"capability.lexical", "capability.identity_fold"})
    for method_id in ("method.crawl_discovery", "method.fetch_document", "method.extract_candidate_evidence"):
        assert methods.latest(method_id).parameter_schema.get("required", []) == []


def test_identity_task_plans_local_identity_search_and_validates_cleanly():
    methods, providers = registries()
    plan = asyncio.run(
        DeterministicPlanner().plan(task(SearchIntent.RESOLVE_IDENTITY), state(), methods.snapshot(), providers.snapshot())
    )
    assert len(plan.nodes) == 1
    node = plan.nodes[0]
    assert isinstance(node, ActionNode)
    assert node.action.method_ref.id == "method.identity_search"
    assert node.action.provider_ref.id == "provider.local_corpus"
    assert node.action.parameters == {"query": "find Alpha Engine"}
    assert node.action.created_at == "2026-08-31T07:00:00+00:00"
    crawler = providers.get_provider(VersionRef("provider.crawler", "1.0.0"))
    assert crawler.surfaces[0].kind is SurfaceKind.WEB_UI
    result = PlanValidator().validate(plan, methods.snapshot(), providers.snapshot())
    assert result.valid, result.issues


def test_unsupported_intent_fails_instead_of_guessing():
    methods, providers = registries()
    with pytest.raises(PlanningError, match="unsupported intent"):
        asyncio.run(
            DeterministicPlanner().plan(task(SearchIntent.RESEARCH), state(), methods.snapshot(), providers.snapshot())
        )
