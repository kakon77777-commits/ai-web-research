import pytest

from ai_web_research.stopping.evaluator import StopEvaluator
from ai_web_research.stopping.models import (
    CoverageAxis,
    CoverageMeasure,
    CoverageState,
    SaturationState,
    SearchBudget,
    SearchProgressSample,
    StopContext,
    StopDisposition,
    StopPolicy,
    StopReason,
    UncertaintyState,
)


def progress(gain: float = 1.0, *, not_found_count: int = 0) -> SearchProgressSample:
    return SearchProgressSample(
        epoch_index=2,
        new_candidates=0,
        new_independent_source_roots=0,
        new_verified_evidence=0,
        material_gap_reduction=0,
        coverage_gain=0.0,
        marginal_gain=gain,
        not_found_count=not_found_count,
    )


def make_context(
    *,
    gaps=("gap-1",),
    gap_assessed=True,
    coverage_met=False,
    saturated=False,
    human_review=False,
    policy_blocked=False,
    providers_available=True,
    actions_used=1,
    max_actions=10,
    cost_used=0.1,
    max_cost=5.0,
    elapsed_ms=100.0,
    max_elapsed_ms=10_000.0,
    samples=None,
):
    measure = CoverageMeasure(
        CoverageAxis.EVIDENCE,
        achieved=2 if coverage_met else 1,
        target=2,
        required=True,
    )
    return StopContext(
        task_id="task-1",
        epoch_id="epoch-1",
        budget=SearchBudget(
            max_actions=max_actions,
            max_cost=max_cost,
            max_elapsed_ms=max_elapsed_ms,
            actions_used=actions_used,
            cost_used=cost_used,
            elapsed_ms=elapsed_ms,
        ),
        coverage=CoverageState(
            measures=(measure,),
            open_material_gap_refs=tuple(gaps),
            material_gap_assessment_complete=gap_assessed,
        ),
        saturation=SaturationState(
            saturated=saturated,
            recent_gains=(0.0, 0.0, 0.0) if saturated else (1.0,),
            reason_codes=("LOW_MARGINAL_GAIN_WINDOW",) if saturated else ("MARGINAL_GAIN_ABOVE_THRESHOLD",),
            scope_note="bounded to current methods/providers/budget",
        ),
        uncertainty=UncertaintyState(
            score=0.8 if human_review else 0.3,
            material_unknown_refs=("unknown-1",) if human_review else (),
            requires_human_review=human_review,
        ),
        progress_samples=tuple(samples or (progress(),)),
        providers_available=providers_available,
        policy_blocked=policy_blocked,
    )


def evaluate(context, **policy_kwargs):
    return StopEvaluator().evaluate(
        context,
        StopPolicy(policy_id="stop.v0.5", **policy_kwargs),
    )


def test_human_review_has_highest_precedence():
    result = evaluate(make_context(
        human_review=True,
        policy_blocked=True,
        providers_available=False,
        actions_used=10,
        max_actions=10,
    ))
    assert result.disposition is StopDisposition.REVIEW
    assert result.reason is StopReason.HUMAN_REVIEW_REQUIRED


def test_policy_block_precedes_provider_and_budget():
    result = evaluate(make_context(
        policy_blocked=True,
        providers_available=False,
        actions_used=10,
        max_actions=10,
    ))
    assert result.disposition is StopDisposition.STOP
    assert result.reason is StopReason.POLICY_BLOCKED


def test_provider_unavailable_precedes_budget():
    result = evaluate(make_context(
        providers_available=False,
        actions_used=10,
        max_actions=10,
    ))
    assert result.reason is StopReason.PROVIDER_UNAVAILABLE


def test_time_limit_is_distinct_from_action_or_cost_budget():
    result = evaluate(make_context(elapsed_ms=10_000, max_elapsed_ms=10_000))
    assert result.reason is StopReason.TIME_LIMIT_REACHED


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        ({"actions_used": 10, "max_actions": 10}, "ACTION_BUDGET_EXHAUSTED"),
        ({"cost_used": 5.0, "max_cost": 5.0}, "COST_BUDGET_EXHAUSTED"),
    ],
)
def test_non_time_budget_exhaustion_is_explicit(kwargs, expected_code):
    result = evaluate(make_context(**kwargs))
    assert result.reason is StopReason.BUDGET_EXHAUSTED
    assert expected_code in result.reason_codes


def test_empty_gap_list_without_completed_assessment_does_not_stop():
    result = evaluate(make_context(gaps=(), gap_assessed=False))
    assert result.disposition is StopDisposition.CONTINUE
    assert result.reason is StopReason.CONTINUE_SEARCH


def test_confirmed_no_material_gap_stops():
    result = evaluate(make_context(gaps=(), gap_assessed=True))
    assert result.disposition is StopDisposition.STOP
    assert result.reason is StopReason.NO_MATERIAL_GAP_REMAINS


def test_terminal_coverage_policy_can_stop_without_claiming_complete_recall():
    result = evaluate(
        make_context(coverage_met=True, gaps=("gap-nonmaterial-or-accepted",)),
        coverage_target_is_terminal=True,
    )
    assert result.reason is StopReason.COVERAGE_TARGET_MET
    assert "COMPLETE_RECALL" not in result.reason_codes


def test_saturation_stops_only_when_required_coverage_is_met():
    result = evaluate(make_context(coverage_met=True, saturated=True))
    assert result.disposition is StopDisposition.STOP
    assert result.reason is StopReason.SATURATION_REACHED
    assert "COMPLETE_RECALL" not in result.reason_codes


def test_saturation_with_unmet_required_coverage_requests_replan():
    result = evaluate(make_context(coverage_met=False, saturated=True))
    assert result.disposition is StopDisposition.REPLAN
    assert result.reason is StopReason.MARGINAL_GAIN_BELOW_THRESHOLD
    assert "COVERAGE_INCOMPLETE" in result.reason_codes


def test_not_found_alone_is_not_false_and_does_not_stop():
    result = evaluate(make_context(
        saturated=False,
        samples=(progress(1.0, not_found_count=3),),
    ))
    assert result.disposition is StopDisposition.CONTINUE
    assert result.reason is StopReason.CONTINUE_SEARCH
    assert "NOT_FOUND_IS_NOT_FALSE" in result.reason_codes
    assert "FALSE" not in result.reason.value


def test_unknown_provider_state_does_not_equal_no_provider():
    result = evaluate(make_context(providers_available=None))
    assert result.disposition is StopDisposition.CONTINUE
    assert result.reason is StopReason.CONTINUE_SEARCH
