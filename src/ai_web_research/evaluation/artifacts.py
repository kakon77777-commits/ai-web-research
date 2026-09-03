from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json

from .models import BenchmarkDataset, BenchmarkReport, BenchmarkSpec
from .runner import dataset_snapshot_id, run_benchmark, spec_snapshot_id


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
class BenchmarkReproducibilityManifest:
    manifest_id: str
    benchmark_id: str
    artifact_format_version: str
    runner_version: str
    spec_snapshot_id: str
    dataset_snapshot_id: str
    report_id: str
    synthetic: bool


class ReproducibilityMismatch(RuntimeError):
    pass


def benchmark_report_json(report: BenchmarkReport) -> str:
    return _stable_json(report)


def manifest_json(manifest: BenchmarkReproducibilityManifest) -> str:
    return _stable_json(manifest)


def build_reproducibility_manifest(
    spec: BenchmarkSpec,
    dataset: BenchmarkDataset,
    report: BenchmarkReport,
) -> BenchmarkReproducibilityManifest:
    expected_spec = spec_snapshot_id(spec)
    expected_dataset = dataset_snapshot_id(dataset)
    if report.spec_snapshot_id != expected_spec:
        raise ValueError("report/spec snapshot mismatch")
    if report.dataset_snapshot_id != expected_dataset:
        raise ValueError("report/dataset snapshot mismatch")
    if report.benchmark_id != spec.benchmark_id:
        raise ValueError("report benchmark_id mismatch")
    if report.runner_version != spec.runner_version:
        raise ValueError("report runner_version mismatch")

    payload = {
        "benchmark_id": spec.benchmark_id,
        "artifact_format_version": "0.8.0",
        "runner_version": spec.runner_version,
        "spec_snapshot_id": expected_spec,
        "dataset_snapshot_id": expected_dataset,
        "report_id": report.report_id,
        "synthetic": spec.synthetic,
    }
    return BenchmarkReproducibilityManifest(
        manifest_id=_hash("benchmark-manifest", payload),
        **payload,
    )


def verify_benchmark_replay(
    spec: BenchmarkSpec,
    dataset: BenchmarkDataset,
    manifest: BenchmarkReproducibilityManifest,
) -> BenchmarkReport:
    current_spec = spec_snapshot_id(spec)
    if current_spec != manifest.spec_snapshot_id:
        raise ReproducibilityMismatch(
            f"spec snapshot mismatch: {current_spec} != {manifest.spec_snapshot_id}"
        )

    current_dataset = dataset_snapshot_id(dataset)
    if current_dataset != manifest.dataset_snapshot_id:
        raise ReproducibilityMismatch(
            "dataset snapshot mismatch: "
            f"{current_dataset} != {manifest.dataset_snapshot_id}"
        )

    report = run_benchmark(spec, dataset)
    if report.report_id != manifest.report_id:
        raise ReproducibilityMismatch(
            f"report mismatch: {report.report_id} != {manifest.report_id}"
        )
    return report
