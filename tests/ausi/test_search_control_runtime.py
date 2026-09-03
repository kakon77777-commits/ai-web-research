from dataclasses import dataclass

from ai_web_research.core.types import RiskClass, SearchIntent, SearchState, SearchTask
from ai_web_research.planning.graph import ActionNode, SearchPlan, StopNode
from ai_web_research.planning.validator import PlanValidator
from ai_web_research.stopping.control import SearchControlRuntime
from ai_web_research.stopping.models import (
    CoverageAxis,
    CoverageMeasure,
    CoverageState,
    SaturationState,
    SearchBudget,
    StopContext,
    StopDisposition,
    StopPolicy,
    UncertaintyState,
)


def task():
    return SearchTask(
        task_id="task-1",
        raw_request="research the claim",
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
        budget={},
        domain_pack=None,
        metadata={},
    )


def state():
    return SearchState(
        task_id="task-1",
        epoch_id="epoch-1",
        planned_at="2026-09-03T08:00:00+00:00",
        active_artifacts=[],
        candidate_refs=[],
        evidence_refs=[],
        open_gap_refs=[],
        completed_action_ids=[],
        failed_action_ids=[],
        budget_state={},
        coverage_state={},
        metadata={},
    )


def context(*, gaps=("gap-1",), gap_assessed=True, coverage_met=False, saturated=False, review=False):
    return StopContext(
        task_id="task-1",
        epoch_id="epoch-1",
        budget=SearchBudget(10, 5.0, 10_000.0, 1, 0.1, 100.0),
        coverage=CoverageState(
            measures=(CoverageMeasure(CoverageAxis.EVIDENCE, 2 if coverage_met else 1, 2),),
            open_material_gap_refs=tuple(gaps),
            material_gap_assessment_complete=gap_assessed,
        ),
        saturation=SaturationState(
            saturated=saturated,
            recent_gains=(0.0, 0.0, 0.0) if saturated else (1.0,),
            reason_codes=("LOW_MARGINAL_GAIN_WINDOW",) if saturated else ("MARGINAL_GAIN_ABOVE_THRESHOLD",),
            scope_note="bounded to current methods/providers/budget",
        ),
        uncertainty=UncertaintyState(0.9 if review else 0.2, (), review),
        progress_samples=(),
        providers_available=True,
        policy_blocked=False,
    )


@dataclass
class DummyPlanningResult:
    plan: SearchPlan


class RecordingPlanner:
    def __init__(self):
        self.calls = []

    def plan(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        planned = SearchPlan(
            plan_id="planner-plan",
            task_id="task-1",
            epoch_id="epoch-1",
            nodes=(),
            edges=(),
            entry_node_ids=(),
            metadata={"planner_id": "dummy"},
        )
        return DummyPlanningResult(planned)


def call(runtime, stop_context):
    return runtime.plan_or_stop(
        task(),
        state(),
        methods=object(),
        corpus=object(),
        providers=object(),
        provider_states=object(),
        routing_policy=object(),
        planning_policy=object(),
        stop_context=stop_context,
        stop_policy=StopPolicy(policy_id="stop.v0.5"),
    )


def test_stop_emits_one_stop_node_and_does_not_call_planner():
    planner = RecordingPlanner()
    result = call(SearchControlRuntime(planner=planner), context(gaps=(), gap_assessed=True))
    assert result.stop_evaluation.disposition is StopDisposition.STOP
    assert result.planning_result is None
    assert planner.calls == []
    assert len(result.plan.nodes) == 1
    assert isinstance(result.plan.nodes[0], StopNode)
    assert result.plan.nodes[0].stop.reason == "NO_MATERIAL_GAP_REMAINS"
    assert result.plan.entry_node_ids == (result.plan.nodes[0].node_id,)
    assert result.plan.metadata["stopping"]["coverage"]["material_gap_assessment_complete"] is True
    assert result.plan.metadata["stopping"]["reason"] == "NO_MATERIAL_GAP_REMAINS"
    assert "credential" not in repr(result.plan.metadata["stopping"]).lower()
    assert PlanValidator().validate(result.plan, object(), object()).valid is True


def test_review_emits_stop_node_with_review_reason_and_does_not_call_planner():
    planner = RecordingPlanner()
    result = call(SearchControlRuntime(planner=planner), context(review=True))
    assert result.stop_evaluation.disposition is StopDisposition.REVIEW
    assert planner.calls == []
    assert isinstance(result.plan.nodes[0], StopNode)
    assert result.plan.nodes[0].stop.reason == "HUMAN_REVIEW_REQUIRED"


def test_continue_delegates_to_existing_planner_without_rewriting_plan():
    planner = RecordingPlanner()
    result = call(SearchControlRuntime(planner=planner), context())
    assert result.stop_evaluation.disposition is StopDisposition.CONTINUE
    assert len(planner.calls) == 1
    assert result.planning_result is not None
    assert result.plan.plan_id == "planner-plan"


def test_low_gain_replan_delegates_to_existing_planner():
    planner = RecordingPlanner()
    result = call(SearchControlRuntime(planner=planner), context(saturated=True, coverage_met=False))
    assert result.stop_evaluation.disposition is StopDisposition.REPLAN
    assert len(planner.calls) == 1
    assert result.plan.plan_id == "planner-plan"
