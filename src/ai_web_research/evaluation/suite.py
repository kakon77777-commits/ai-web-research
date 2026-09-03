from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json

from .artifacts import (
    BenchmarkReproducibilityManifest,
    build_reproducibility_manifest,
)
from .models import BenchmarkReport
from .reference import ReferenceBenchmarkSuite
from .runner import run_benchmark


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise TypeError(type(value).__name__)


def _stable_json(value) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash(prefix: str, value) -> str:
    return f"{prefix}:{sha256(_stable_json(value).encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class BenchmarkSuiteRun:
    suite_id: str
    suite_version: str
    synthetic: bool
    reports: tuple[BenchmarkReport, ...]
    benchmark_manifests: tuple[BenchmarkReproducibilityManifest, ...]
    suite_report_id: str


@dataclass(frozen=True)
class BenchmarkSuiteManifest:
    manifest_id: str
    artifact_format_version: str
    suite_id: str
    suite_version: str
    synthetic: bool
    fixture_sha256: str
    suite_report_id: str
    benchmark_manifest_ids: tuple[str, ...]


def run_reference_benchmark_suite(
    suite: ReferenceBenchmarkSuite,
) -> BenchmarkSuiteRun:
    pairs = []
    for item in sorted(suite.benchmarks, key=lambda x: x.spec.benchmark_id):
        report = run_benchmark(item.spec, item.dataset)
        manifest = build_reproducibility_manifest(
            item.spec,
            item.dataset,
            report,
        )
        pairs.append((report, manifest))

    reports = tuple(report for report, _ in pairs)
    manifests = tuple(manifest for _, manifest in pairs)
    payload = {
        "suite_id": suite.suite_id,
        "suite_version": suite.suite_version,
        "synthetic": suite.synthetic,
        "report_ids": [item.report_id for item in reports],
        "benchmark_manifest_ids": [
            item.manifest_id for item in manifests
        ],
    }
    return BenchmarkSuiteRun(
        suite_id=suite.suite_id,
        suite_version=suite.suite_version,
        synthetic=suite.synthetic,
        reports=reports,
        benchmark_manifests=manifests,
        suite_report_id=_hash("benchmark-suite-report", payload),
    )


def build_suite_manifest(
    run: BenchmarkSuiteRun,
    *,
    fixture_sha256: str,
) -> BenchmarkSuiteManifest:
    normalized = fixture_sha256.lower()
    if len(normalized) != 64 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise ValueError("fixture_sha256 must be a 64-character hex digest")

    payload = {
        "artifact_format_version": "0.8.0",
        "suite_id": run.suite_id,
        "suite_version": run.suite_version,
        "synthetic": run.synthetic,
        "fixture_sha256": normalized,
        "suite_report_id": run.suite_report_id,
        "benchmark_manifest_ids": [
            item.manifest_id for item in run.benchmark_manifests
        ],
    }
    return BenchmarkSuiteManifest(
        manifest_id=_hash("benchmark-suite-manifest", payload),
        artifact_format_version="0.8.0",
        suite_id=run.suite_id,
        suite_version=run.suite_version,
        synthetic=run.synthetic,
        fixture_sha256=normalized,
        suite_report_id=run.suite_report_id,
        benchmark_manifest_ids=tuple(
            item.manifest_id for item in run.benchmark_manifests
        ),
    )


def suite_report_json(run: BenchmarkSuiteRun) -> str:
    return _stable_json(run)


def suite_manifest_json(manifest: BenchmarkSuiteManifest) -> str:
    return _stable_json(manifest)
