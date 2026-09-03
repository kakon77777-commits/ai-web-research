from __future__ import annotations

from .models import (
    StopContext,
    StopDisposition,
    StopEvaluation,
    StopPolicy,
    StopReason,
)


class StopEvaluator:
    def evaluate(self, context: StopContext, policy: StopPolicy) -> StopEvaluation:
        if context.uncertainty.requires_human_review:
            return self._result(
                context,
                StopDisposition.REVIEW,
                StopReason.HUMAN_REVIEW_REQUIRED,
                "HUMAN_REVIEW_REQUIRED",
            )

        if context.policy_blocked:
            return self._result(
                context,
                StopDisposition.STOP,
                StopReason.POLICY_BLOCKED,
                "POLICY_BLOCKED",
            )

        if context.providers_available is False:
            return self._result(
                context,
                StopDisposition.STOP,
                StopReason.PROVIDER_UNAVAILABLE,
                "PROVIDER_UNAVAILABLE",
            )

        if context.budget.time_budget_exhausted:
            return self._result(
                context,
                StopDisposition.STOP,
                StopReason.TIME_LIMIT_REACHED,
                "TIME_BUDGET_EXHAUSTED",
            )

        if context.budget.non_time_budget_exhausted:
            reasons: list[str] = []
            if context.budget.action_budget_exhausted:
                reasons.append("ACTION_BUDGET_EXHAUSTED")
            if context.budget.cost_budget_exhausted:
                reasons.append("COST_BUDGET_EXHAUSTED")
            return StopEvaluation(
                disposition=StopDisposition.STOP,
                reason=StopReason.BUDGET_EXHAUSTED,
                reason_codes=tuple(reasons),
                context=context,
            )

        if context.coverage.confirmed_no_material_gaps:
            return self._result(
                context,
                StopDisposition.STOP,
                StopReason.NO_MATERIAL_GAP_REMAINS,
                "MATERIAL_GAP_ASSESSMENT_COMPLETE",
                "NO_OPEN_MATERIAL_GAP",
            )

        if (
            policy.coverage_target_is_terminal
            and context.coverage.has_required_targets
            and context.coverage.required_targets_met
        ):
            return self._result(
                context,
                StopDisposition.STOP,
                StopReason.COVERAGE_TARGET_MET,
                "COVERAGE_TARGETS_MET",
                "TERMINAL_COVERAGE_POLICY",
            )

        if context.saturation.saturated:
            if (
                policy.allow_saturation_stop
                and context.coverage.has_required_targets
                and context.coverage.required_targets_met
            ):
                return self._result(
                    context,
                    StopDisposition.STOP,
                    StopReason.SATURATION_REACHED,
                    "SATURATION_UNDER_CURRENT_SCOPE",
                    "COVERAGE_TARGETS_MET",
                )

            if policy.replan_on_low_gain:
                reasons = ["LOW_MARGINAL_GAIN_WINDOW"]
                if not context.coverage.required_targets_met:
                    reasons.append("COVERAGE_INCOMPLETE")
                return StopEvaluation(
                    disposition=StopDisposition.REPLAN,
                    reason=StopReason.MARGINAL_GAIN_BELOW_THRESHOLD,
                    reason_codes=tuple(reasons),
                    context=context,
                )

        reasons: list[str] = []
        if any(sample.not_found_count > 0 for sample in context.progress_samples):
            reasons.append("NOT_FOUND_IS_NOT_FALSE")
        if context.coverage.open_material_gap_refs:
            reasons.append("OPEN_MATERIAL_GAPS")
        elif not context.coverage.material_gap_assessment_complete:
            reasons.append("MATERIAL_GAP_ASSESSMENT_INCOMPLETE")
        if not reasons:
            reasons.append("CONTINUE_SEARCH")

        return StopEvaluation(
            disposition=StopDisposition.CONTINUE,
            reason=StopReason.CONTINUE_SEARCH,
            reason_codes=tuple(reasons),
            context=context,
        )

    @staticmethod
    def _result(
        context: StopContext,
        disposition: StopDisposition,
        reason: StopReason,
        *reason_codes: str,
    ) -> StopEvaluation:
        return StopEvaluation(
            disposition=disposition,
            reason=reason,
            reason_codes=tuple(reason_codes),
            context=context,
        )
