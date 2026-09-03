from pathlib import Path

from ai_web_research.experience.receipt import SearchReceiptRecorder, SearchReceiptStatus
from ai_web_research.experience.sqlite import SearchReceiptStore
from ai_web_research.stopping.evaluator import StopEvaluator
from ai_web_research.stopping.models import (
    CoverageAxis,
    CoverageMeasure,
    CoverageState,
    SaturationPolicy,
    SearchBudget,
    SearchProgressSample,
    StopContext,
    StopDisposition,
    StopPolicy,
    StopReason,
    UncertaintyState,
)
from ai_web_research.stopping.progress import assess_saturation
from ai_web_research.stopping.receipt import stopping_receipt_metadata


def sample(i: int, gain: float, *, not_found=0):
    return SearchProgressSample(
        epoch_index=i,
        new_candidates=0,
        new_independent_source_roots=0,
        new_verified_evidence=0,
        material_gap_reduction=0,
        coverage_gain=0.0,
        marginal_gain=gain,
        not_found_count=not_found,
    )


def context(samples, *, coverage_met: bool, gaps=("gap-1",)):
    coverage = CoverageState(
        measures=(
            CoverageMeasure(
                CoverageAxis.EVIDENCE,
                achieved=2 if coverage_met else 1,
                target=2,
                required=True,
            ),
        ),
        open_material_gap_refs=tuple(gaps),
        material_gap_assessment_complete=True,
    )
    saturation = assess_saturation(
        tuple(samples),
        SaturationPolicy(window_size=3, minimum_samples=3, marginal_gain_threshold=0.1),
    )
    return StopContext(
        task_id="task-1",
        epoch_id="epoch-1",
        budget=SearchBudget(10, 5.0, 10_000.0, len(samples), 0.2, 500.0),
        coverage=coverage,
        saturation=saturation,
        uncertainty=UncertaintyState(0.3, (), False),
        progress_samples=tuple(samples),
        providers_available=True,
        policy_blocked=False,
    )


def test_not_found_then_low_gain_then_bounded_saturation_stop_and_receipt(tmp_path: Path):
    evaluator = StopEvaluator()
    policy = StopPolicy(policy_id="stop.v0.5")

    first = evaluator.evaluate(
        context((sample(0, 1.0, not_found=2),), coverage_met=False),
        policy,
    )
    assert first.disposition is StopDisposition.CONTINUE
    assert first.reason is StopReason.CONTINUE_SEARCH
    assert "NOT_FOUND_IS_NOT_FALSE" in first.reason_codes

    low_incomplete = evaluator.evaluate(
        context(
            (sample(0, 0.0, not_found=1), sample(1, 0.05), sample(2, 0.0)),
            coverage_met=False,
        ),
        policy,
    )
    assert low_incomplete.disposition is StopDisposition.REPLAN
    assert low_incomplete.reason is StopReason.MARGINAL_GAIN_BELOW_THRESHOLD
    assert "COVERAGE_INCOMPLETE" in low_incomplete.reason_codes

    bounded_stop = evaluator.evaluate(
        context(
            (sample(0, 0.0), sample(1, 0.05), sample(2, 0.0)),
            coverage_met=True,
        ),
        policy,
    )
    assert bounded_stop.disposition is StopDisposition.STOP
    assert bounded_stop.reason is StopReason.SATURATION_REACHED

    metadata = stopping_receipt_metadata(bounded_stop)
    assert metadata["disposition"] == "stop"
    assert metadata["reason"] == "SATURATION_REACHED"
    assert metadata["coverage"]["required_targets_met"] is True
    assert metadata["saturation"]["saturated"] is True
    assert metadata["saturation"]["scope_note"] == "bounded to current methods/providers/budget"

    serialized = repr(metadata).lower()
    assert "complete_recall" not in serialized
    assert "recall_complete" not in serialized
    assert "credential" not in serialized
    assert "chain_of_thought" not in serialized

    store = SearchReceiptStore(tmp_path / "receipts.sqlite")
    recorder = SearchReceiptRecorder(store)
    receipt = recorder.finalize(
        receipt_id="receipt-1",
        task_id="task-1",
        epoch_id="epoch-1",
        registry_snapshot_id="registry-1",
        planner_id="planner.autonomous.v1",
        planner_version="0.4.0",
        stop_reason=bounded_stop.reason.value,
        status=SearchReceiptStatus.PARTIAL,
        created_at="2026-09-03T08:30:00+00:00",
        metadata={"stopping": metadata},
    )
    loaded = store.get_search_receipt("receipt-1")
    assert receipt.stop_reason == "SATURATION_REACHED"
    assert loaded.stop_reason == "SATURATION_REACHED"
    assert loaded.status is SearchReceiptStatus.PARTIAL
    assert loaded.metadata["stopping"]["saturation"]["saturated"] is True
    store.close()
