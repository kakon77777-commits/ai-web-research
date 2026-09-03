from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import SearchState, SearchTask, StopAction
from ai_web_research.planning.autonomous import AutonomousPlannerV1
from ai_web_research.planning.graph import SearchPlan, StopNode

from .evaluator import StopEvaluator
from .models import StopContext, StopDisposition, StopEvaluation, StopPolicy
from .receipt import stopping_receipt_metadata


@dataclass(frozen=True)
class ControlledPlanningResult:
    stop_evaluation: StopEvaluation
    plan: SearchPlan
    planning_result: object | None


class SearchControlRuntime:
    control_id = "control.stopping.v0.5"
    control_version = "0.5.0"

    def __init__(self, *, planner=None, evaluator=None) -> None:
        self.planner = planner or AutonomousPlannerV1()
        self.evaluator = evaluator or StopEvaluator()

    def plan_or_stop(
        self,
        task: SearchTask,
        state: SearchState,
        *,
        methods,
        corpus,
        providers,
        provider_states,
        routing_policy,
        planning_policy,
        stop_context: StopContext,
        stop_policy: StopPolicy,
        proposal=None,
    ) -> ControlledPlanningResult:
        if task.task_id != state.task_id:
            raise ValueError("task/state task_id mismatch")
        if stop_context.task_id != task.task_id or stop_context.epoch_id != state.epoch_id:
            raise ValueError("stop context does not match task/state")

        evaluation = self.evaluator.evaluate(stop_context, stop_policy)
        if evaluation.disposition in {StopDisposition.STOP, StopDisposition.REVIEW}:
            plan = self._stop_plan(task, state, evaluation)
            return ControlledPlanningResult(
                stop_evaluation=evaluation,
                plan=plan,
                planning_result=None,
            )

        planning_result = self.planner.plan(
            task,
            state,
            methods,
            corpus,
            providers,
            provider_states,
            routing_policy,
            planning_policy,
            proposal=proposal,
        )
        return ControlledPlanningResult(
            stop_evaluation=evaluation,
            plan=planning_result.plan,
            planning_result=planning_result,
        )

    def _stop_plan(
        self,
        task: SearchTask,
        state: SearchState,
        evaluation: StopEvaluation,
    ) -> SearchPlan:
        stop = StopAction(
            action_id=f"{state.epoch_id}:stop:1",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            reason=evaluation.reason.value,
            state_ref=f"{state.epoch_id}:state",
            created_by=self.control_id,
            created_at=state.planned_at,
        )
        node = StopNode(
            node_id=f"{state.epoch_id}:node:stop",
            stop=stop,
        )
        return SearchPlan(
            plan_id=f"{state.epoch_id}:plan:stop",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            nodes=(node,),
            edges=(),
            entry_node_ids=(node.node_id,),
            metadata={
                "control_id": self.control_id,
                "control_version": self.control_version,
                "stop_disposition": evaluation.disposition.value,
                "stop_reason": evaluation.reason.value,
                "stop_reason_codes": list(evaluation.reason_codes),
                "stopping": stopping_receipt_metadata(evaluation),
            },
        )
