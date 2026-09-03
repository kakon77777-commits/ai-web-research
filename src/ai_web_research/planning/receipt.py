from __future__ import annotations

from ai_web_research.core.types import JsonValue
from .autonomous import AutonomousPlanningResult


def planning_receipt_metadata(result: AutonomousPlanningResult) -> dict[str, JsonValue]:
    summary = result.decision_summary
    proposal = result.proposal
    return {
        "proposal_id": proposal.proposal_id,
        "plan_id": result.plan.plan_id,
        "method_corpus_snapshot_id": summary.method_corpus_snapshot_id,
        "provider_state_snapshot_id": summary.provider_state_snapshot_id,
        "selected_method_ids": list(summary.selected_method_ids),
        "skipped_method_ids": list(summary.skipped_method_ids),
        "skip_reasons": [
            {"method_id": method_id, "reason_codes": list(reason_codes)}
            for method_id, reason_codes in summary.skip_reasons
        ],
        "gap_refs": list(summary.gap_refs),
        "objectives": [step.objective for step in proposal.steps],
        "budget": {
            "max_actions": summary.budget.max_actions,
            "max_parallel_branches": summary.budget.max_parallel_branches,
            "max_loop_iterations": summary.budget.max_loop_iterations,
            "max_provider_fallbacks": summary.budget.max_provider_fallbacks,
        },
        "routing": list(summary.routing_summaries),
        "proposal_reason_codes": list(proposal.reason_codes),
        "planner_id": result.plan.metadata.get("planner_id"),
        "planner_version": result.plan.metadata.get("planner_version"),
        "reasoning_omitted": True,
    }
