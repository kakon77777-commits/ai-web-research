from dataclasses import FrozenInstanceError, fields

import pytest

from ai_web_research.core.types import RiskClass, SearchIntent, SearchState, SearchTask
from ai_web_research.planning.autonomous_models import (
    PlanningBudget,
    PlanningDecisionSummary,
    PlanningGap,
    PlanningPolicy,
    ProposedMethodStep,
    SearchStrategyProposal,
    planning_budget_from,
    planning_gaps_from_state,
)


def task(**budget):
    return SearchTask(
        task_id="task-1",
        raw_request="research current AI search systems",
        intent=SearchIntent.RESEARCH,
        domain=None,
        purpose="research",
        languages=("en",),
        jurisdictions=(),
        freshness={},
        coverage_requirements={},
        verification_requirements={},
        source_preferences=(),
        risk_class=RiskClass.LOW,
        budget=budget,
        domain_pack=None,
        metadata={},
    )


def state(*, budget_state=None, open_gaps=(), gap_details=None):
    return SearchState(
        task_id="task-1",
        epoch_id="epoch-1",
        planned_at="2026-09-03T08:00:00+00:00",
        active_artifacts=[],
        candidate_refs=[],
        evidence_refs=[],
        open_gap_refs=list(open_gaps),
        completed_action_ids=[],
        failed_action_ids=[],
        budget_state=dict(budget_state or {}),
        coverage_state={},
        metadata={"gap_details": gap_details or {}},
    )


def test_planning_contracts_are_immutable_and_provider_neutral():
    gap = PlanningGap("gap-1", "source_independence", 10)
    with pytest.raises(FrozenInstanceError):
        gap.priority = 1

    step = ProposedMethodStep(
        step_id="discover",
        objective="discover_candidates",
        candidate_method_ids=("method.lexical_search",),
        reason_codes=("TASK_RESEARCH",),
    )
    proposal = SearchStrategyProposal(
        proposal_id="proposal-1",
        task_id="task-1",
        steps=(step,),
        replan_condition_ref="open_gaps_remain",
        max_replans=2,
        reason_codes=("OPEN_GAPS",),
    )
    assert proposal.steps[0].candidate_method_ids == ("method.lexical_search",)

    forbidden = {
        "provider_id", "provider_ref", "binding_id", "surface_id",
        "api_key", "access_token", "credential", "password",
        "chain_of_thought", "private_reasoning",
    }
    proposal_fields = {item.name for item in fields(ProposedMethodStep)} | {item.name for item in fields(SearchStrategyProposal)}
    assert not proposal_fields.intersection(forbidden)


def test_budget_intersection_uses_stricter_task_and_runtime_limits():
    result = planning_budget_from(
        task(max_actions=8, max_parallel_branches=4, max_loop_iterations=3, max_provider_fallbacks=2),
        state(budget_state={
            "max_actions": 5,
            "max_parallel_branches": 2,
            "max_loop_iterations": 2,
            "max_provider_fallbacks": 1,
        }),
    )
    assert result == PlanningBudget(
        max_actions=5,
        max_parallel_branches=2,
        max_loop_iterations=2,
        max_provider_fallbacks=1,
    )


def test_budget_defaults_are_bounded_and_invalid_values_do_not_expand_them():
    result = planning_budget_from(
        task(max_actions=-100, max_parallel_branches="many"),
        state(budget_state={"max_loop_iterations": 0}),
    )
    assert result.max_actions == 4
    assert result.max_parallel_branches == 2
    assert result.max_loop_iterations == 2
    assert result.max_provider_fallbacks == 1


def test_gap_view_uses_only_open_gap_refs_and_explicit_metadata():
    gaps = planning_gaps_from_state(state(
        open_gaps=("gap-source", "gap-evidence", "gap-unknown"),
        gap_details={
            "gap-source": {"type": "source_independence", "priority": 20},
            "gap-evidence": {"type": "evidence_missing", "priority": 10},
            "closed-gap": {"type": "identity_unresolved", "priority": 99},
        },
    ))
    assert gaps == (
        PlanningGap("gap-source", "source_independence", 20),
        PlanningGap("gap-evidence", "evidence_missing", 10),
        PlanningGap("gap-unknown", "unknown", 0),
    )


def test_planning_policy_and_summary_have_no_authorization_or_secret_fields():
    policy = PlanningPolicy(policy_id="planner-policy.v1")
    assert policy.allow_experimental is False
    assert policy.enable_provider_fallback is True

    names = {item.name for item in fields(PlanningDecisionSummary)}
    assert "policy_decision" not in names
    assert "authorization" not in names
    assert "credential" not in names
    assert "chain_of_thought" not in names
