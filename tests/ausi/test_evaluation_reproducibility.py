import json

import pytest

from ai_web_research.evaluation.artifacts import (
    ReproducibilityMismatch,
    benchmark_report_json,
    build_reproducibility_manifest,
    manifest_json,
    verify_benchmark_replay,
)
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


def spec():
    return BenchmarkSpec(
        benchmark_id="bench.replay",
        family=BenchmarkFamily.REPLAY_REPRODUCIBILITY,
        title="Replay",
        baseline_variant_id="base",
        candidate_variant_ids=("candidate",),
        metrics=(
            MetricDefinition("success_rate", MetricDirection.HIGHER_IS_BETTER, "ratio"),
            MetricDefinition("avg_cost", MetricDirection.LOWER_IS_BETTER, "cost"),
        ),
        synthetic=True,
        description="synthetic replay benchmark",
        runner_version="0.8.0",
        metadata={"suite": "reference"},
    )


def observation(case, variant, cost):
    return BenchmarkTrialObservation(
        case_id=case,
        variant_id=variant,
        status=BenchmarkTrialStatus.SUCCESS,
        provider_failure=False,
        candidate_yield=1,
        verified_evidence_yield=1,
        independent_root_yield=1,
        gap_reduction=1,
        raw_source_mentions=1,
        cost=cost,
        latency_ms=10,
        actions=1,
        replans=0,
        metadata={},
    )


def dataset(*, candidate_cost=1.0, reverse=False):
    observations = (
        observation("c1", "base", 2.0),
        observation("c2", "base", 2.0),
        observation("c1", "candidate", candidate_cost),
        observation("c2", "candidate", candidate_cost),
    )
    if reverse:
        observations = tuple(reversed(observations))
    return BenchmarkDataset(
        dataset_id="dataset.replay",
        dataset_version="0.8.0",
        observations=observations,
        metadata={},
    )


def test_report_json_is_stable_and_machine_readable():
    a = run_benchmark(spec(), dataset())
    b = run_benchmark(spec(), dataset(reverse=True))
    left = benchmark_report_json(a)
    right = benchmark_report_json(b)
    assert left == right
    parsed = json.loads(left)
    assert parsed["report_id"] == a.report_id
    assert parsed["family"] == "replay_reproducibility"
    assert parsed["synthetic"] is True


def test_manifest_is_content_addressed_and_stable():
    report = run_benchmark(spec(), dataset())
    a = build_reproducibility_manifest(spec(), dataset(), report)
    b = build_reproducibility_manifest(spec(), dataset(reverse=True), report)

    assert a == b
    assert a.manifest_id.startswith("benchmark-manifest:")
    assert a.spec_snapshot_id == report.spec_snapshot_id
    assert a.dataset_snapshot_id == report.dataset_snapshot_id
    assert a.report_id == report.report_id
    assert a.artifact_format_version == "0.8.0"
    parsed = json.loads(manifest_json(a))
    assert parsed["manifest_id"] == a.manifest_id


def test_exact_replay_matches_manifest():
    report = run_benchmark(spec(), dataset())
    manifest = build_reproducibility_manifest(spec(), dataset(), report)
    replay = verify_benchmark_replay(spec(), dataset(reverse=True), manifest)
    assert replay.report_id == report.report_id


def test_changed_dataset_fails_replay_gate():
    report = run_benchmark(spec(), dataset())
    manifest = build_reproducibility_manifest(spec(), dataset(), report)
    with pytest.raises(ReproducibilityMismatch, match="dataset"):
        verify_benchmark_replay(
            spec(),
            dataset(candidate_cost=1.1),
            manifest,
        )


def test_changed_runner_or_spec_fails_replay_gate():
    report = run_benchmark(spec(), dataset())
    manifest = build_reproducibility_manifest(spec(), dataset(), report)
    changed = BenchmarkSpec(**{**spec().__dict__, "runner_version": "0.8.1"})
    with pytest.raises(ReproducibilityMismatch, match="spec"):
        verify_benchmark_replay(changed, dataset(), manifest)
