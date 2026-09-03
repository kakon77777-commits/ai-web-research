from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Callable

from .models import (
    BenchmarkComparison,
    BenchmarkDataset,
    BenchmarkReport,
    BenchmarkSpec,
    BenchmarkTrialObservation,
    BenchmarkTrialStatus,
    MetricAggregate,
    MetricDirection,
    VariantSummary,
    validate_benchmark_dataset,
)


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field: _canonical(getattr(value, field))
            for field in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise TypeError(type(value).__name__)


def _hash(prefix: str, payload) -> str:
    encoded = json.dumps(
        _canonical(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}:{sha256(encoded).hexdigest()}"


def spec_snapshot_id(spec: BenchmarkSpec) -> str:
    return _hash("benchmark-spec", spec)


def dataset_snapshot_id(dataset: BenchmarkDataset) -> str:
    ordered = tuple(
        sorted(
            dataset.observations,
            key=lambda item: (item.variant_id, item.case_id),
        )
    )
    payload = {
        "dataset_id": dataset.dataset_id,
        "dataset_version": dataset.dataset_version,
        "observations": ordered,
        "metadata": dataset.metadata,
    }
    return _hash("benchmark-dataset", payload)


def _average_known(
    observations: tuple[BenchmarkTrialObservation, ...],
    getter: Callable[[BenchmarkTrialObservation], float | int | None],
) -> tuple[float | None, int]:
    values = [
        float(value)
        for item in observations
        if (value := getter(item)) is not None
    ]
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def _metric_value(
    metric_id: str,
    observations: tuple[BenchmarkTrialObservation, ...],
) -> tuple[float | None, int]:
    total = len(observations)
    if metric_id == "success_rate":
        value = sum(
            item.status is BenchmarkTrialStatus.SUCCESS
            for item in observations
        ) / total
        return value, total

    if metric_id == "provider_failure_rate":
        return sum(item.provider_failure for item in observations) / total, total

    average_fields = {
        "avg_candidate_yield": lambda item: item.candidate_yield,
        "avg_verified_evidence_yield": lambda item: item.verified_evidence_yield,
        "avg_independent_root_yield": lambda item: item.independent_root_yield,
        "avg_gap_reduction": lambda item: item.gap_reduction,
        "avg_cost": lambda item: item.cost,
        "avg_latency_ms": lambda item: item.latency_ms,
        "avg_actions": lambda item: item.actions,
        "avg_replans": lambda item: item.replans,
    }
    if metric_id in average_fields:
        return _average_known(observations, average_fields[metric_id])

    if metric_id == "source_overcount":
        return _average_known(
            observations,
            lambda item: (
                item.raw_source_mentions - item.independent_root_yield
                if item.raw_source_mentions is not None
                and item.independent_root_yield is not None
                else None
            ),
        )

    if metric_id == "source_independence_ratio":
        return _average_known(
            observations,
            lambda item: (
                item.independent_root_yield / item.raw_source_mentions
                if item.raw_source_mentions not in (None, 0)
                and item.independent_root_yield is not None
                else None
            ),
        )

    raise ValueError(f"unsupported benchmark metric: {metric_id}")


def _summary(
    variant_id: str,
    spec: BenchmarkSpec,
    dataset: BenchmarkDataset,
) -> VariantSummary:
    observations = tuple(
        sorted(
            (
                item
                for item in dataset.observations
                if item.variant_id == variant_id
            ),
            key=lambda item: item.case_id,
        )
    )
    metrics = []
    for definition in spec.metrics:
        value, known_count = _metric_value(definition.metric_id, observations)
        metrics.append(
            MetricAggregate(
                metric_id=definition.metric_id,
                value=value,
                known_count=known_count,
                total_count=len(observations),
            )
        )
    return VariantSummary(
        variant_id=variant_id,
        case_ids=tuple(item.case_id for item in observations),
        metrics=tuple(metrics),
    )


def _comparison(
    baseline: VariantSummary,
    candidate: VariantSummary,
    definition,
) -> BenchmarkComparison:
    base_value = baseline.metric(definition.metric_id).value
    candidate_value = candidate.metric(definition.metric_id).value

    if base_value is None or candidate_value is None:
        delta = None
        relative_delta = None
        candidate_better = None
    else:
        delta = candidate_value - base_value
        relative_delta = delta / base_value if base_value != 0 else None
        if definition.direction is MetricDirection.HIGHER_IS_BETTER:
            candidate_better = candidate_value > base_value
        elif definition.direction is MetricDirection.LOWER_IS_BETTER:
            candidate_better = candidate_value < base_value
        else:
            candidate_better = None

    return BenchmarkComparison(
        candidate_variant_id=candidate.variant_id,
        metric_id=definition.metric_id,
        direction=definition.direction,
        baseline_value=base_value,
        candidate_value=candidate_value,
        delta=delta,
        relative_delta=relative_delta,
        candidate_better=candidate_better,
    )


def run_benchmark(spec: BenchmarkSpec, dataset: BenchmarkDataset) -> BenchmarkReport:
    validate_benchmark_dataset(spec, dataset)

    summaries = tuple(
        _summary(variant_id, spec, dataset)
        for variant_id in spec.variant_ids
    )
    baseline = summaries[0]
    comparisons = tuple(
        _comparison(baseline, candidate, definition)
        for candidate in summaries[1:]
        for definition in spec.metrics
    )
    spec_id = spec_snapshot_id(spec)
    dataset_id = dataset_snapshot_id(dataset)

    report_without_id = {
        "benchmark_id": spec.benchmark_id,
        "family": spec.family,
        "baseline_variant_id": spec.baseline_variant_id,
        "spec_snapshot_id": spec_id,
        "dataset_snapshot_id": dataset_id,
        "runner_version": spec.runner_version,
        "synthetic": spec.synthetic,
        "summaries": summaries,
        "comparisons": comparisons,
        "metadata": {
            "paired_case_count": len(baseline.case_ids),
        },
    }
    report_id = _hash("benchmark-report", report_without_id)
    return BenchmarkReport(
        report_id=report_id,
        **report_without_id,
    )
