from __future__ import annotations

from ai_web_research.core.types import JsonValue

from .models import StopEvaluation


def stopping_receipt_metadata(evaluation: StopEvaluation) -> dict[str, JsonValue]:
    context = evaluation.context
    return {
        "disposition": evaluation.disposition.value,
        "reason": evaluation.reason.value,
        "reason_codes": list(evaluation.reason_codes),
        "budget": {
            "max_actions": context.budget.max_actions,
            "max_cost": context.budget.max_cost,
            "max_elapsed_ms": context.budget.max_elapsed_ms,
            "actions_used": context.budget.actions_used,
            "cost_used": context.budget.cost_used,
            "elapsed_ms": context.budget.elapsed_ms,
            "action_budget_exhausted": context.budget.action_budget_exhausted,
            "cost_budget_exhausted": context.budget.cost_budget_exhausted,
            "time_budget_exhausted": context.budget.time_budget_exhausted,
        },
        "coverage": {
            "measures": [
                {
                    "axis": measure.axis.value,
                    "achieved": measure.achieved,
                    "target": measure.target,
                    "required": measure.required,
                    "met": measure.met,
                }
                for measure in context.coverage.measures
            ],
            "open_material_gap_refs": list(context.coverage.open_material_gap_refs),
            "material_gap_assessment_complete": context.coverage.material_gap_assessment_complete,
            "has_required_targets": context.coverage.has_required_targets,
            "required_targets_met": context.coverage.required_targets_met,
            "unmet_required_axes": [
                axis.value for axis in context.coverage.unmet_required_axes
            ],
        },
        "saturation": {
            "saturated": context.saturation.saturated,
            "recent_gains": list(context.saturation.recent_gains),
            "reason_codes": list(context.saturation.reason_codes),
            "scope_note": context.saturation.scope_note,
        },
        "uncertainty": {
            "score": context.uncertainty.score,
            "material_unknown_refs": list(context.uncertainty.material_unknown_refs),
            "requires_human_review": context.uncertainty.requires_human_review,
        },
        "progress": {
            "sample_count": len(context.progress_samples),
            "not_found_count": sum(
                sample.not_found_count for sample in context.progress_samples
            ),
        },
        "providers_available": context.providers_available,
        "policy_blocked": context.policy_blocked,
    }
