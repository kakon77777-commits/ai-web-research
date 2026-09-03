from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .models import (
    BenchmarkDataset,
    BenchmarkFamily,
    BenchmarkSpec,
    BenchmarkTrialObservation,
    BenchmarkTrialStatus,
    MetricDefinition,
    MetricDirection,
    validate_benchmark_dataset,
)


@dataclass(frozen=True)
class ReferenceBenchmark:
    spec: BenchmarkSpec
    dataset: BenchmarkDataset


@dataclass(frozen=True)
class ReferenceBenchmarkSuite:
    suite_id: str
    suite_version: str
    synthetic: bool
    description: str
    benchmarks: tuple[ReferenceBenchmark, ...]


def _metric(data: dict) -> MetricDefinition:
    return MetricDefinition(
        metric_id=data["metric_id"],
        direction=MetricDirection(data["direction"]),
        unit=data["unit"],
    )


def _spec(data: dict) -> BenchmarkSpec:
    return BenchmarkSpec(
        benchmark_id=data["benchmark_id"],
        family=BenchmarkFamily(data["family"]),
        title=data["title"],
        baseline_variant_id=data["baseline_variant_id"],
        candidate_variant_ids=tuple(data["candidate_variant_ids"]),
        metrics=tuple(_metric(item) for item in data["metrics"]),
        synthetic=bool(data["synthetic"]),
        description=data["description"],
        runner_version=data["runner_version"],
        metadata=dict(data.get("metadata") or {}),
    )


def _observation(data: dict) -> BenchmarkTrialObservation:
    return BenchmarkTrialObservation(
        case_id=data["case_id"],
        variant_id=data["variant_id"],
        status=BenchmarkTrialStatus(data["status"]),
        provider_failure=bool(data["provider_failure"]),
        candidate_yield=data.get("candidate_yield"),
        verified_evidence_yield=data.get("verified_evidence_yield"),
        independent_root_yield=data.get("independent_root_yield"),
        gap_reduction=data.get("gap_reduction"),
        raw_source_mentions=data.get("raw_source_mentions"),
        cost=data.get("cost"),
        latency_ms=data.get("latency_ms"),
        actions=data.get("actions"),
        replans=data.get("replans"),
        metadata=dict(data.get("metadata") or {}),
    )


def _dataset(data: dict) -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_id=data["dataset_id"],
        dataset_version=data["dataset_version"],
        observations=tuple(_observation(item) for item in data["observations"]),
        metadata=dict(data.get("metadata") or {}),
    )


def load_reference_suite(path: Path) -> ReferenceBenchmarkSuite:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("canonical reference suite must be explicitly synthetic")

    benchmarks = []
    for raw in data["benchmarks"]:
        spec = _spec(raw["spec"])
        dataset = _dataset(raw["dataset"])
        if not spec.synthetic:
            raise ValueError(
                f"reference benchmark {spec.benchmark_id} must be marked synthetic"
            )
        validate_benchmark_dataset(spec, dataset)
        benchmarks.append(ReferenceBenchmark(spec=spec, dataset=dataset))

    families = tuple(item.spec.family for item in benchmarks)
    if len(set(families)) != len(families):
        raise ValueError("duplicate benchmark family in reference suite")

    return ReferenceBenchmarkSuite(
        suite_id=data["suite_id"],
        suite_version=data["suite_version"],
        synthetic=True,
        description=data["description"],
        benchmarks=tuple(benchmarks),
    )
