from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue


class BenchmarkFamily(StrEnum):
    PROVIDER_SUBSTITUTION = "provider_substitution"
    METHOD_DIVERSITY = "method_diversity"
    ADAPTIVE_PLANNING = "adaptive_planning"
    PROVENANCE_INDEPENDENCE = "provenance_independence"
    REPLAY_REPRODUCIBILITY = "replay_reproducibility"


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


class BenchmarkTrialStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    REVIEW = "review"


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    direction: MetricDirection
    unit: str

    def __post_init__(self) -> None:
        if not self.metric_id.strip():
            raise ValueError("metric_id must be non-empty")
        if not self.unit.strip():
            raise ValueError("unit must be non-empty")


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_id: str
    family: BenchmarkFamily
    title: str
    baseline_variant_id: str
    candidate_variant_ids: tuple[str, ...]
    metrics: tuple[MetricDefinition, ...]
    synthetic: bool
    description: str
    runner_version: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("benchmark_id", self.benchmark_id),
            ("title", self.title),
            ("baseline_variant_id", self.baseline_variant_id),
            ("description", self.description),
            ("runner_version", self.runner_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.candidate_variant_ids:
            raise ValueError("at least one candidate variant is required")
        if self.baseline_variant_id in self.candidate_variant_ids:
            raise ValueError("baseline variant cannot also be a candidate")
        if len(set(self.candidate_variant_ids)) != len(self.candidate_variant_ids):
            raise ValueError("duplicate candidate variant")
        metric_ids = tuple(metric.metric_id for metric in self.metrics)
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("duplicate metric")
        if not self.metrics:
            raise ValueError("at least one metric is required")

    @property
    def variant_ids(self) -> tuple[str, ...]:
        return (self.baseline_variant_id, *self.candidate_variant_ids)


@dataclass(frozen=True)
class BenchmarkTrialObservation:
    case_id: str
    variant_id: str
    status: BenchmarkTrialStatus
    provider_failure: bool
    candidate_yield: int | None
    verified_evidence_yield: int | None
    independent_root_yield: int | None
    gap_reduction: int | None
    raw_source_mentions: int | None
    cost: float | None
    latency_ms: float | None
    actions: int | None
    replans: int | None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not self.variant_id.strip():
            raise ValueError("variant_id must be non-empty")

        values = {
            "candidate_yield": self.candidate_yield,
            "verified_evidence_yield": self.verified_evidence_yield,
            "independent_root_yield": self.independent_root_yield,
            "gap_reduction": self.gap_reduction,
            "raw_source_mentions": self.raw_source_mentions,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "actions": self.actions,
            "replans": self.replans,
        }
        for name, value in values.items():
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0 when known")
        if (
            self.raw_source_mentions is not None
            and self.independent_root_yield is not None
            and self.independent_root_yield > self.raw_source_mentions
        ):
            raise ValueError(
                "independent_root_yield cannot exceed raw_source_mentions "
                "when both are measured in the same benchmark trial"
            )


@dataclass(frozen=True)
class BenchmarkDataset:
    dataset_id: str
    dataset_version: str
    observations: tuple[BenchmarkTrialObservation, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must be non-empty")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must be non-empty")
        if not self.observations:
            raise ValueError("observations must be non-empty")
        keys = tuple((item.variant_id, item.case_id) for item in self.observations)
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate variant/case observation")


@dataclass(frozen=True)
class MetricAggregate:
    metric_id: str
    value: float | None
    known_count: int
    total_count: int


@dataclass(frozen=True)
class VariantSummary:
    variant_id: str
    case_ids: tuple[str, ...]
    metrics: tuple[MetricAggregate, ...]

    def metric(self, metric_id: str) -> MetricAggregate:
        for metric in self.metrics:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(metric_id)


@dataclass(frozen=True)
class BenchmarkComparison:
    candidate_variant_id: str
    metric_id: str
    direction: MetricDirection
    baseline_value: float | None
    candidate_value: float | None
    delta: float | None
    relative_delta: float | None
    candidate_better: bool | None


@dataclass(frozen=True)
class BenchmarkReport:
    report_id: str
    benchmark_id: str
    family: BenchmarkFamily
    baseline_variant_id: str
    spec_snapshot_id: str
    dataset_snapshot_id: str
    runner_version: str
    synthetic: bool
    summaries: tuple[VariantSummary, ...]
    comparisons: tuple[BenchmarkComparison, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)


def validate_benchmark_dataset(spec: BenchmarkSpec, dataset: BenchmarkDataset) -> None:
    allowed = set(spec.variant_ids)
    seen_variants = {item.variant_id for item in dataset.observations}
    unknown = sorted(seen_variants - allowed)
    if unknown:
        raise ValueError(f"unknown variant(s): {unknown}")

    missing_variants = sorted(allowed - seen_variants)
    if missing_variants:
        raise ValueError(f"missing variant(s): {missing_variants}")

    baseline_cases = {
        item.case_id
        for item in dataset.observations
        if item.variant_id == spec.baseline_variant_id
    }
    for variant_id in spec.candidate_variant_ids:
        cases = {
            item.case_id
            for item in dataset.observations
            if item.variant_id == variant_id
        }
        if cases != baseline_cases:
            raise ValueError(
                f"paired case mismatch for {variant_id}: "
                f"baseline={sorted(baseline_cases)} candidate={sorted(cases)}"
            )
