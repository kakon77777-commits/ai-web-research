from dataclasses import fields

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, SearchIntent, SearchState, SearchTask
from ai_web_research.planning.autonomous_models import PlanningBudget, planning_gaps_from_state
from ai_web_research.planning.proposal import RuleProposalSource


def make_task(intent=SearchIntent.RESEARCH):
    return SearchTask(
        task_id="task-1", raw_request="research AI search systems", intent=intent,
        domain=None, purpose="research", languages=("en",), jurisdictions=(),
        freshness={}, coverage_requirements={}, verification_requirements={}, source_preferences=(),
        risk_class=RiskClass.LOW, budget={}, domain_pack=None, metadata={},
    )


def make_state(*, gaps=(), details=None, artifacts=None, candidates=None):
    return SearchState(
        task_id="task-1", epoch_id="epoch-1", planned_at="2026-09-03T08:00:00+00:00",
        active_artifacts=list(artifacts or []), candidate_refs=list(candidates or []), evidence_refs=[],
        open_gap_refs=list(gaps), completed_action_ids=[], failed_action_ids=[], budget_state={},
        coverage_state={}, metadata={"gap_details": details or {}},
    )


def test_research_proposal_uses_lexical_and_query_divergence_without_providers():
    proposal = RuleProposalSource().propose(
        make_task(), make_state(), (), PlanningBudget(max_actions=4, max_parallel_branches=2),
    )
    assert [(step.objective, step.candidate_method_ids) for step in proposal.steps] == [
        ("discover_candidates", ("method.lexical_search",)),
        ("diversify_queries", ("method.query_divergence",)),
    ]
    forbidden = {"provider_id", "provider_ref", "binding_id", "surface_id", "credential", "api_key"}
    names = {item.name for step in proposal.steps for item in fields(step)}
    assert not names.intersection(forbidden)


def test_identity_intent_proposes_identity_search_only():
    proposal = RuleProposalSource().propose(
        make_task(SearchIntent.RESOLVE_IDENTITY), make_state(), (), PlanningBudget(),
    )
    assert len(proposal.steps) == 1
    assert proposal.steps[0].candidate_method_ids == ("method.identity_search",)


def test_gap_directed_proposal_adds_identity_fetch_extract_and_counter_search():
    state = make_state(
        gaps=("g-counter", "g-id", "g-fetch", "g-evidence"),
        details={
            "g-counter": {"type": "counter_evidence", "priority": 40},
            "g-id": {"type": "identity_unresolved", "priority": 30},
            "g-fetch": {"type": "candidate_acquisition", "priority": 20},
            "g-evidence": {"type": "evidence_missing", "priority": 10},
        },
        artifacts=(ArtifactRef(ArtifactKind.DOCUMENT, "doc-1"),),
        candidates=("candidate-1",),
    )
    proposal = RuleProposalSource().propose(
        make_task(), state, planning_gaps_from_state(state), PlanningBudget(max_actions=8, max_parallel_branches=8),
    )
    by_objective = {step.objective: step for step in proposal.steps}
    assert by_objective["find_counter_evidence"].candidate_method_ids == (
        "method.counter_evidence_search", "method.lexical_search"
    )
    assert by_objective["resolve_identity"].candidate_method_ids == ("method.identity_search",)
    assert by_objective["acquire_candidate"].candidate_method_ids == ("method.fetch_document",)
    assert by_objective["extract_evidence"].candidate_method_ids == ("method.extract_candidate_evidence",)
    assert proposal.replan_condition_ref == "open_gaps_remain"
    assert proposal.max_replans == 1


def test_evidence_gap_does_not_invent_document_input():
    state = make_state(
        gaps=("g-evidence",),
        details={"g-evidence": {"type": "evidence_missing", "priority": 10}},
    )
    proposal = RuleProposalSource().propose(
        make_task(), state, planning_gaps_from_state(state), PlanningBudget(max_actions=5, max_parallel_branches=5),
    )
    assert "extract_evidence" not in {step.objective for step in proposal.steps}


def test_budget_caps_number_of_proposed_steps_deterministically():
    state = make_state(
        gaps=("g-id", "g-counter"),
        details={
            "g-id": {"type": "identity_unresolved", "priority": 20},
            "g-counter": {"type": "counter_evidence", "priority": 10},
        },
    )
    proposal = RuleProposalSource().propose(
        make_task(), state, planning_gaps_from_state(state), PlanningBudget(max_actions=2, max_parallel_branches=2),
    )
    assert len(proposal.steps) == 2
    assert [step.objective for step in proposal.steps] == ["resolve_identity", "find_counter_evidence"]
