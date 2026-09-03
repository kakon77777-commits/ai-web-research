import math

from ai_web_research.evaluation.models import (
    BenchmarkDataset,
    BenchmarkFamily,
    BenchmarkSpec,
    BenchmarkTrialObservation,
    BenchmarkTrialStatus,
    MetricDirection,
    MetricDefinition,
)
from ai_web_research.evaluation.runner import run_benchmark


def spec(metrics):
    return BenchmarkSpec(
        benchmark_id="bench.test",
        family=BenchmarkFamily.PROVIDER_SUBSTITUTION,
        title="Test",
        baseline_variant_id="base",
        candidate_variant_ids=("candidate",),
        metrics=tuple(metrics),
        synthetic=True,
        description="synthetic",
        runner_version="0.8.0",
        metadata={},
    )


def obs(
    case, variant, *,
    status=BenchmarkTrialStatus.SUCCESS,
    provider_failure=False,
    candidates=None,
    evidence=None,
    roots=None,
    gaps=None,
    mentions=None,
    cost=None,
    latency=None,
    actions=None,
    replans=None,
):
    return BenchmarkTrialObservation(
        case_id=case,
        variant_id=variant,
        status=status,
        provider_failure=provider_failure,
        candidate_yield=candidates,
        verified_evidence_yield=evidence,
        independent_root_yield=roots,
        gap_reduction=gaps,
        raw_source_mentions=mentions,
        cost=cost,
        latency_ms=latency,
        actions=actions,
        replans=replans,
        metadata={},
    )


def test_runner_aggregates_supported_metrics_and_known_counts():
    metrics = (
        MetricDefinition("success_rate", MetricDirection.HIGHER_IS_BETTER, "ratio"),
        MetricDefinition("provider_failure_rate", MetricDirection.LOWER_IS_BETTER, "ratio"),
        MetricDefinition("avg_verified_evidence_yield", MetricDirection.HIGHER_IS_BETTER, "count"),
        MetricDefinition("avg_cost", MetricDirection.LOWER_IS_BETTER, "cost"),
        MetricDefinition("avg_latency_ms", MetricDirection.LOWER_IS_BETTER, "ms"),
    )
    dataset = BenchmarkDataset(
        dataset_id="d1",
        dataset_version="0.8.0",
        observations=(
            obs("c1", "base", status=BenchmarkTrialStatus.FAILED, provider_failure=True, evidence=None, cost=2.0, latency=100),
            obs("c2", "base", evidence=1, cost=None, latency=200),
            obs("c1", "candidate", evidence=2, cost=1.0, latency=80),
            obs("c2", "candidate", evidence=4, cost=1.5, latency=120),
        ),
        metadata={},
    )
    report = run_benchmark(spec(metrics), dataset)
    base = next(x for x in report.summaries if x.variant_id == "base")
    cand = next(x for x in report.summaries if x.variant_id == "candidate")

    assert base.metric("success_rate").value == 0.5
    assert base.metric("provider_failure_rate").value == 0.5
    assert base.metric("avg_verified_evidence_yield").value == 1.0
    assert base.metric("avg_verified_evidence_yield").known_count == 1
    assert base.metric("avg_verified_evidence_yield").total_count == 2
    assert base.metric("avg_cost").known_count == 1
    assert base.metric("avg_cost").value == 2.0
    assert cand.metric("avg_verified_evidence_yield").value == 3.0
    assert cand.metric("avg_latency_ms").value == 100.0


def test_comparison_uses_metric_direction_and_transparent_relative_delta():
    metrics = (
        MetricDefinition("success_rate", MetricDirection.HIGHER_IS_BETTER, "ratio"),
        MetricDefinition("avg_cost", MetricDirection.LOWER_IS_BETTER, "cost"),
    )
    dataset = BenchmarkDataset(
        dataset_id="d1",
        dataset_version="0.8.0",
        observations=(
            obs("c1", "base", status=BenchmarkTrialStatus.FAILED, cost=4),
            obs("c2", "base", status=BenchmarkTrialStatus.SUCCESS, cost=4),
            obs("c1", "candidate", cost=2),
            obs("c2", "candidate", cost=2),
        ),
        metadata={},
    )
    report = run_benchmark(spec(metrics), dataset)
    comparisons = {item.metric_id: item for item in report.comparisons}

    success = comparisons["success_rate"]
    assert success.baseline_value == 0.5
    assert success.candidate_value == 1.0
    assert success.delta == 0.5
    assert success.relative_delta == 1.0
    assert success.candidate_better is True

    cost = comparisons["avg_cost"]
    assert cost.baseline_value == 4.0
    assert cost.candidate_value == 2.0
    assert cost.delta == -2.0
    assert cost.relative_delta == -0.5
    assert cost.candidate_better is True


def test_unknown_metric_value_stays_unknown_in_summary_and_comparison():
    metrics = (
        MetricDefinition("avg_cost", MetricDirection.LOWER_IS_BETTER, "cost"),
    )
    dataset = BenchmarkDataset(
        dataset_id="d1",
        dataset_version="0.8.0",
        observations=(
            obs("c1", "base", cost=None),
            obs("c1", "candidate", cost=1.0),
        ),
        metadata={},
    )
    report = run_benchmark(spec(metrics), dataset)
    base = next(x for x in report.summaries if x.variant_id == "base")
    comparison = report.comparisons[0]

    assert base.metric("avg_cost").value is None
    assert base.metric("avg_cost").known_count == 0
    assert comparison.baseline_value is None
    assert comparison.delta is None
    assert comparison.relative_delta is None
    assert comparison.candidate_better is None


def test_zero_baseline_has_defined_delta_but_no_relative_delta():
    metrics = (
        MetricDefinition("avg_gap_reduction", MetricDirection.HIGHER_IS_BETTER, "count"),
    )
    dataset = BenchmarkDataset(
        dataset_id="d1",
        dataset_version="0.8.0",
        observations=(
            obs("c1", "base", gaps=0),
            obs("c1", "candidate", gaps=2),
        ),
        metadata={},
    )
    comparison = run_benchmark(spec(metrics), dataset).comparisons[0]
    assert comparison.delta == 2.0
    assert comparison.relative_delta is None
    assert comparison.candidate_better is True


def test_provenance_metrics_expose_raw_source_overcount_and_independence_ratio():
    metrics = (
        MetricDefinition("source_overcount", MetricDirection.LOWER_IS_BETTER, "count"),
        MetricDefinition("source_independence_ratio", MetricDirection.HIGHER_IS_BETTER, "ratio"),
    )
    dataset = BenchmarkDataset(
        dataset_id="d1",
        dataset_version="0.8.0",
        observations=(
            obs("c1", "base", mentions=5, roots=2),
            obs("c1", "candidate", mentions=2, roots=2),
        ),
        metadata={},
    )
    report = run_benchmark(spec(metrics), dataset)
    base = next(x for x in report.summaries if x.variant_id == "base")
    cand = next(x for x in report.summaries if x.variant_id == "candidate")

    assert base.metric("source_overcount").value == 3.0
    assert base.metric("source_independence_ratio").value == 0.4
    assert cand.metric("source_overcount").value == 0.0
    assert cand.metric("source_independence_ratio").value == 1.0
    assert all(item.candidate_better is True for item in report.comparisons)


def test_runner_report_identity_is_input_order_independent():
    metrics = (
        MetricDefinition("success_rate", MetricDirection.HIGHER_IS_BETTER, "ratio"),
    )
    observations = (
        obs("c1", "base"),
        obs("c2", "base"),
        obs("c1", "candidate"),
        obs("c2", "candidate"),
    )
    left = BenchmarkDataset("d1", "0.8.0", observations, {})
    right = BenchmarkDataset("d1", "0.8.0", tuple(reversed(observations)), {})
    a = run_benchmark(spec(metrics), left)
    b = run_benchmark(spec(metrics), right)
    assert a.spec_snapshot_id == b.spec_snapshot_id
    assert a.dataset_snapshot_id == b.dataset_snapshot_id
    assert a.report_id == b.report_id
