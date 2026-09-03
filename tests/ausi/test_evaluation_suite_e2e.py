import hashlib
import json
from pathlib import Path

from ai_web_research.evaluation.artifacts import verify_benchmark_replay
from ai_web_research.evaluation.reference import load_reference_suite
from ai_web_research.evaluation.suite import (
    build_suite_manifest,
    run_reference_benchmark_suite,
    suite_manifest_json,
    suite_report_json,
)


FIXTURE = Path("benchmarks/omphalos-v0.8-reference-suite.json")
REPORT = Path("benchmarks/artifacts/omphalos-v0.8-reference-report.json")
MANIFEST = Path("benchmarks/artifacts/omphalos-v0.8-reference-manifest.json")


def test_reference_suite_runs_all_five_families_and_is_content_addressed():
    suite = load_reference_suite(FIXTURE)
    run = run_reference_benchmark_suite(suite)

    assert len(run.reports) == 5
    assert len(run.benchmark_manifests) == 5
    assert run.synthetic is True
    assert run.suite_report_id.startswith("benchmark-suite-report:")
    assert len({x.report_id for x in run.reports}) == 5


def test_every_reference_benchmark_manifest_replays():
    suite = load_reference_suite(FIXTURE)
    run = run_reference_benchmark_suite(suite)
    manifest_by_benchmark = {
        item.benchmark_id: item for item in run.benchmark_manifests
    }
    for item in suite.benchmarks:
        replay = verify_benchmark_replay(
            item.spec,
            item.dataset,
            manifest_by_benchmark[item.spec.benchmark_id],
        )
        assert replay.report_id == manifest_by_benchmark[item.spec.benchmark_id].report_id


def test_suite_artifacts_exactly_regenerate_repository_outputs():
    suite = load_reference_suite(FIXTURE)
    run = run_reference_benchmark_suite(suite)
    fixture_sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    manifest = build_suite_manifest(run, fixture_sha256=fixture_sha)

    regenerated_report = suite_report_json(run) + "\n"
    regenerated_manifest = suite_manifest_json(manifest) + "\n"

    assert REPORT.read_text(encoding="utf-8") == regenerated_report
    assert MANIFEST.read_text(encoding="utf-8") == regenerated_manifest

    parsed = json.loads(regenerated_manifest)
    assert parsed["fixture_sha256"] == fixture_sha
    assert parsed["synthetic"] is True
    assert parsed["suite_report_id"] == run.suite_report_id


def test_suite_identity_is_stable():
    suite = load_reference_suite(FIXTURE)
    a = run_reference_benchmark_suite(suite)
    b = run_reference_benchmark_suite(suite)
    assert a == b
    assert suite_report_json(a) == suite_report_json(b)
