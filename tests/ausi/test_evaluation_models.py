from dataclasses import FrozenInstanceError

import pytest

from ai_web_research.evaluation.models import (
    BenchmarkDataset,
    BenchmarkFamily,
    BenchmarkSpec,
    BenchmarkTrialObservation,
    BenchmarkTrialStatus,
    MetricDirection,
    MetricDefinition,
    validate_benchmark_dataset,
)


def spec():
    return BenchmarkSpec(
        benchmark_id="bench.provider-substitution.v0.8",
        family=BenchmarkFamily.PROVIDER_SUBSTITUTION,
        title="Provider substitution",
        baseline_variant_id="single",
        candidate_variant_ids=("hybrid",),
        metrics=(
            MetricDefinition("success_rate", MetricDirection.HIGHER_IS_BETTER, "ratio"),
            MetricDefinition("avg_cost", MetricDirection.LOWER_IS_BETTER, "cost"),
        ),
        synthetic=True,
        description="synthetic mechanism benchmark",
        runner_version="0.8.0",
        metadata={},
    )


def obs(case, variant, *, status=BenchmarkTrialStatus.SUCCESS, cost=None):
    return BenchmarkTrialObservation(
        case_id=case,
        variant_id=variant,
        status=status,
        provider_failure=False,
        candidate_yield=None,
        verified_evidence_yield=None,
        independent_root_yield=None,
        gap_reduction=None,
        raw_source_mentions=None,
        cost=cost,
        latency_ms=None,
        actions=None,
        replans=None,
        metadata={},
    )


def test_benchmark_families_and_metric_direction_are_explicit():
    assert {x.value for x in BenchmarkFamily} == {
        "provider_substitution",
        "method_diversity",
        "adaptive_planning",
        "provenance_independence",
        "replay_reproducibility",
    }
    assert MetricDirection.HIGHER_IS_BETTER.value == "higher_is_better"
    assert MetricDirection.LOWER_IS_BETTER.value == "lower_is_better"


def test_spec_is_immutable_and_rejects_ambiguous_variants_or_metrics():
    item = spec()
    with pytest.raises(FrozenInstanceError):
        item.synthetic = False

    with pytest.raises(ValueError, match="baseline"):
        BenchmarkSpec(**{**item.__dict__, "candidate_variant_ids": ("single",)})

    with pytest.raises(ValueError, match="duplicate metric"):
        BenchmarkSpec(**{
            **item.__dict__,
            "metrics": (
                MetricDefinition("x", MetricDirection.HIGHER_IS_BETTER, "count"),
                MetricDefinition("x", MetricDirection.LOWER_IS_BETTER, "count"),
            ),
        })


def test_trial_observation_preserves_unknown_metrics_as_none():
    item = obs("case-1", "single")
    assert item.candidate_yield is None
    assert item.verified_evidence_yield is None
    assert item.cost is None
    assert item.latency_ms is None


@pytest.mark.parametrize(
    "field",
    [
        "candidate_yield",
        "verified_evidence_yield",
        "independent_root_yield",
        "gap_reduction",
        "raw_source_mentions",
        "cost",
        "latency_ms",
        "actions",
        "replans",
    ],
)
def test_trial_observation_rejects_negative_observable_values(field):
    values = obs("case-1", "single").__dict__.copy()
    values[field] = -1
    with pytest.raises(ValueError):
        BenchmarkTrialObservation(**values)


def test_dataset_rejects_duplicate_variant_case_pairs():
    with pytest.raises(ValueError, match="duplicate"):
        BenchmarkDataset(
            dataset_id="dataset:1",
            dataset_version="0.8.0",
            observations=(
                obs("case-1", "single"),
                obs("case-1", "single"),
            ),
            metadata={},
        )


def test_dataset_validation_requires_same_paired_cases_for_every_variant():
    dataset = BenchmarkDataset(
        dataset_id="dataset:1",
        dataset_version="0.8.0",
        observations=(
            obs("case-1", "single"),
            obs("case-2", "single"),
            obs("case-1", "hybrid"),
        ),
        metadata={},
    )
    with pytest.raises(ValueError, match="paired case"):
        validate_benchmark_dataset(spec(), dataset)


def test_dataset_validation_rejects_unknown_variant():
    dataset = BenchmarkDataset(
        dataset_id="dataset:1",
        dataset_version="0.8.0",
        observations=(
            obs("case-1", "single"),
            obs("case-1", "hybrid"),
            obs("case-1", "mystery"),
        ),
        metadata={},
    )
    with pytest.raises(ValueError, match="unknown variant"):
        validate_benchmark_dataset(spec(), dataset)


def test_balanced_dataset_passes_validation():
    dataset = BenchmarkDataset(
        dataset_id="dataset:1",
        dataset_version="0.8.0",
        observations=(
            obs("case-1", "single"),
            obs("case-2", "single"),
            obs("case-1", "hybrid"),
            obs("case-2", "hybrid"),
        ),
        metadata={},
    )
    validate_benchmark_dataset(spec(), dataset)
