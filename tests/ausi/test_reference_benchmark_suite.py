from pathlib import Path

from ai_web_research.evaluation.artifacts import (
    build_reproducibility_manifest,
    verify_benchmark_replay,
)
from ai_web_research.evaluation.models import BenchmarkFamily
from ai_web_research.evaluation.reference import load_reference_suite
from ai_web_research.evaluation.runner import run_benchmark


FIXTURE = Path("benchmarks/omphalos-v0.8-reference-suite.json")
README = Path("benchmarks/README.md")


def suite():
    return load_reference_suite(FIXTURE)


def report_for(family):
    item = next(x for x in suite().benchmarks if x.spec.family is family)
    return item, run_benchmark(item.spec, item.dataset)


def comparison(report, metric_id):
    return next(x for x in report.comparisons if x.metric_id == metric_id)


def test_reference_suite_is_explicitly_synthetic_and_covers_all_families():
    item = suite()
    assert item.synthetic is True
    assert {x.spec.family for x in item.benchmarks} == set(BenchmarkFamily)
    assert all(x.spec.synthetic is True for x in item.benchmarks)


def test_provider_substitution_reference_exposes_resilience_tradeoff():
    _, report = report_for(BenchmarkFamily.PROVIDER_SUBSTITUTION)
    assert comparison(report, "success_rate").candidate_better is True
    assert comparison(report, "provider_failure_rate").candidate_better is True
    assert comparison(report, "avg_verified_evidence_yield").candidate_better is True


def test_method_diversity_reference_exposes_evidence_and_gap_gain():
    _, report = report_for(BenchmarkFamily.METHOD_DIVERSITY)
    assert comparison(report, "avg_verified_evidence_yield").candidate_better is True
    assert comparison(report, "avg_gap_reduction").candidate_better is True
    assert comparison(report, "success_rate").candidate_better is True


def test_adaptive_planning_reference_exposes_gap_and_efficiency_difference():
    _, report = report_for(BenchmarkFamily.ADAPTIVE_PLANNING)
    assert comparison(report, "avg_gap_reduction").candidate_better is True
    assert comparison(report, "avg_actions").candidate_better is True
    assert comparison(report, "avg_cost").candidate_better is True
    assert comparison(report, "avg_latency_ms").candidate_better is True


def test_provenance_reference_detects_source_family_overcount():
    _, report = report_for(BenchmarkFamily.PROVENANCE_INDEPENDENCE)
    assert comparison(report, "source_overcount").candidate_better is True
    assert comparison(report, "source_independence_ratio").candidate_better is True


def test_replay_reference_is_stable_under_observation_reordering():
    item, report = report_for(BenchmarkFamily.REPLAY_REPRODUCIBILITY)
    manifest = build_reproducibility_manifest(item.spec, item.dataset, report)
    reversed_dataset = item.dataset.__class__(
        dataset_id=item.dataset.dataset_id,
        dataset_version=item.dataset.dataset_version,
        observations=tuple(reversed(item.dataset.observations)),
        metadata=item.dataset.metadata,
    )
    replay = verify_benchmark_replay(item.spec, reversed_dataset, manifest)
    assert replay.report_id == report.report_id
    assert all(x.delta == 0 for x in replay.comparisons)


def test_reference_readme_disclaims_live_superiority_claim():
    text = README.read_text(encoding="utf-8").lower()
    assert "synthetic" in text
    assert "does not demonstrate live-web superiority" in text
    assert "live provider" in text
