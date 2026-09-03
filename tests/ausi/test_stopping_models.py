from dataclasses import FrozenInstanceError, fields

import pytest

from ai_web_research.stopping.models import (
    CoverageAxis,
    CoverageMeasure,
    CoverageState,
    SaturationPolicy,
    SaturationState,
    SearchBudget,
    SearchProgressSample,
    StopContext,
    StopDisposition,
    StopEvaluation,
    StopPolicy,
    StopReason,
    UncertaintyState,
)


def test_coverage_axes_are_explicit_and_required_targets_are_not_vacuously_met():
    assert {axis.value for axis in CoverageAxis} == {
        "method", "provider", "source", "evidence",
        "jurisdiction", "language", "temporal", "domain",
    }
    empty = CoverageState(measures=(), open_material_gap_refs=("gap-1",))
    assert empty.has_required_targets is False
    assert empty.required_targets_met is False

    state = CoverageState(
        measures=(
            CoverageMeasure(CoverageAxis.SOURCE, achieved=2, target=2),
            CoverageMeasure(CoverageAxis.LANGUAGE, achieved=1, target=2),
            CoverageMeasure(CoverageAxis.PROVIDER, achieved=1, target=5, required=False),
        ),
        open_material_gap_refs=("gap-1",),
    )
    assert state.has_required_targets is True
    assert state.required_targets_met is False
    assert state.unmet_required_axes == (CoverageAxis.LANGUAGE,)


def test_budget_exhaustion_is_typed_and_separates_time_from_action_cost():
    budget = SearchBudget(
        max_actions=4,
        max_cost=2.0,
        max_elapsed_ms=1000.0,
        actions_used=4,
        cost_used=1.0,
        elapsed_ms=500.0,
    )
    assert budget.action_budget_exhausted is True
    assert budget.cost_budget_exhausted is False
    assert budget.time_budget_exhausted is False
    assert budget.non_time_budget_exhausted is True


def test_saturation_state_never_contains_complete_recall_claim():
    names = {f.name for f in fields(SaturationState)}
    assert "complete_recall" not in names
    assert "recall_complete" not in names
    state = SaturationState(
        saturated=True,
        recent_gains=(0.0, 0.0, 0.0),
        reason_codes=("LOW_MARGINAL_GAIN_WINDOW",),
        scope_note="bounded to current methods/providers/budget",
    )
    assert "complete" not in state.scope_note.lower()


def test_progress_and_uncertainty_contracts_validate_observable_values():
    sample = SearchProgressSample(
        epoch_index=3,
        new_candidates=0,
        new_independent_source_roots=0,
        new_verified_evidence=0,
        material_gap_reduction=0,
        coverage_gain=0.0,
        marginal_gain=0.0,
        not_found_count=2,
    )
    assert sample.not_found_count == 2

    with pytest.raises(ValueError):
        UncertaintyState(score=1.1, material_unknown_refs=(), requires_human_review=False)
    with pytest.raises(ValueError):
        SearchProgressSample(
            epoch_index=-1,
            new_candidates=0,
            new_independent_source_roots=0,
            new_verified_evidence=0,
            material_gap_reduction=0,
            coverage_gain=0.0,
            marginal_gain=0.0,
        )


def test_stop_contracts_are_immutable_and_reason_space_is_explicit():
    assert StopReason.SATURATION_REACHED.value == "SATURATION_REACHED"
    assert StopReason.MARGINAL_GAIN_BELOW_THRESHOLD.value == "MARGINAL_GAIN_BELOW_THRESHOLD"
    assert StopDisposition.REPLAN.value == "replan"

    policy = StopPolicy(policy_id="stop.v0.5")
    with pytest.raises(FrozenInstanceError):
        policy.coverage_target_is_terminal = True

    coverage = CoverageState(
        measures=(CoverageMeasure(CoverageAxis.EVIDENCE, 1, 2),),
        open_material_gap_refs=("gap-evidence",),
    )
    saturation = SaturationState(False, (), ("INSUFFICIENT_HISTORY",), "bounded to current methods/providers/budget")
    uncertainty = UncertaintyState(0.5, ("unknown-1",), False)
    budget = SearchBudget(10, 5.0, 10_000.0, 1, 0.2, 500.0)
    context = StopContext(
        task_id="task-1",
        epoch_id="epoch-1",
        budget=budget,
        coverage=coverage,
        saturation=saturation,
        uncertainty=uncertainty,
        progress_samples=(),
        providers_available=True,
        policy_blocked=False,
    )
    evaluation = StopEvaluation(
        disposition=StopDisposition.CONTINUE,
        reason=StopReason.CONTINUE_SEARCH,
        reason_codes=("OPEN_MATERIAL_GAPS",),
        context=context,
    )
    assert evaluation.context.coverage.open_material_gap_refs == ("gap-evidence",)


def test_required_coverage_target_must_be_positive():
    with pytest.raises(ValueError):
        CoverageMeasure(CoverageAxis.EVIDENCE, achieved=0, target=0, required=True)
    optional = CoverageMeasure(CoverageAxis.PROVIDER, achieved=0, target=0, required=False)
    assert optional.met is True


def test_saturated_state_requires_observed_gain_window():
    with pytest.raises(ValueError):
        SaturationState(
            saturated=True,
            recent_gains=(),
            reason_codes=("LOW_MARGINAL_GAIN_WINDOW",),
            scope_note="bounded to current methods/providers/budget",
        )
