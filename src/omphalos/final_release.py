from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib

from .api import build_public_api_manifest
from .release import _find_forbidden_fields, scan_literal_secrets
from .version import PACKAGE_VERSION, PUBLIC_API_VERSION


FINAL_RELEASE_GATE_VERSION = "1.0.0"
FINAL_PACKAGE_VERSION = "1.0.0"
RC_PACKAGE_VERSION = "1.0.0rc1"
RC_MERGE_SHA = "c291567bcc4ec59bacdc90036819e0db264a2f23"

FINAL_PUBLIC_API_ARTIFACT = "release/omphalos-v1.0.0-public-api.json"
FINAL_MANIFEST_ARTIFACT = "release/omphalos-v1.0.0-final-manifest.json"
RC_PUBLIC_API_ARTIFACT = "release/omphalos-v1.0.0rc1-public-api.json"
RC_MANIFEST_ARTIFACT = "release/omphalos-v1.0.0rc1-manifest.json"

RC_PUBLIC_API_SHA256 = "7e46a963e19100c1feac9525ee221b82b98f4dad78a85e25bc55d8a2665763a9"
RC_MANIFEST_SHA256 = "cc5440800ae16ce93a2b2592d8343d77f9811e377287ed1e1c8eadc6bb824c2a"

REQUIRED_RELEASE_DOCS = (
    "docs/QUICKSTART.md",
    "docs/release/API_STABILITY_AND_MIGRATION_v1.md",
    "docs/release/SECURITY_AND_CREDENTIALS_v1.md",
    "docs/release/REFERENCE_WORKFLOWS_v1.md",
    "docs/release/RELEASE_v1.0.0.md",
)

REQUIRED_BENCHMARK_ARTIFACTS = (
    "benchmarks/omphalos-v0.8-reference-suite.json",
    "benchmarks/artifacts/omphalos-v0.8-reference-report.json",
    "benchmarks/artifacts/omphalos-v0.8-reference-manifest.json",
)

GATE_EVIDENCE = {
    "G1_METHOD": (
        "tests/ausi/test_method_registry.py",
        "tests/ausi/test_builtin_method_corpus.py",
        "tests/ausi/test_method_coverage.py",
    ),
    "G2_PROVIDER": (
        "tests/ausi/test_omphalos_identity_topology.py",
        "tests/ausi/test_model_native_providers.py",
    ),
    "G3_REPLACEABILITY": (
        "tests/ausi/test_provider_substitution_e2e.py",
        "tests/ausi/test_dynamic_routing.py",
    ),
    "G4_PLANNER": (
        "tests/ausi/test_autonomous_planner_e2e.py",
        "tests/ausi/test_autonomous_planner_v1.py",
    ),
    "G5_POLICY": (
        "tests/ausi/test_policy_runtime.py",
        "tests/ausi/test_policy_runtime_downstream.py",
        "tests/ausi/test_trusted_execution_runtime.py",
    ),
    "G6_EVIDENCE": (
        "tests/ausi/test_evidence_promotion_gate.py",
        "tests/ausi/test_evidence_provenance_closure_e2e.py",
    ),
    "G7_GAP_STOP": (
        "tests/ausi/test_stopping_e2e.py",
        "tests/ausi/test_search_control_runtime.py",
    ),
    "G8_RECEIPT": (
        "tests/ausi/test_search_receipts.py",
        "tests/ausi/test_experience_store_replay.py",
    ),
    "G9_EVALUATION": (
        "tests/ausi/test_evaluation_suite_e2e.py",
        "tests/ausi/test_evaluation_reproducibility.py",
    ),
}

REFERENCE_WORKFLOW_EVIDENCE = {
    "general_web": (
        "tests/ausi/test_ai_daily_live_discovery_e2e.py",
        "tests/ausi/test_candidate_verification_batch.py",
    ),
    "current_x_web": (
        "tests/ausi/test_model_native_providers.py",
        "tests/ausi/test_ai_daily_live_discovery_e2e.py",
    ),
    "academic_npl": (
        "tests/ausi/test_crossref_trusted_receipt_e2e.py",
    ),
    "patent_prior_art": (
        "tests/ausi/test_software_prior_art_extension_workflow.py",
        "tests/ausi/test_epo_ops_trusted_e2e.py",
    ),
}


class FinalReleaseGateFailure(RuntimeError):
    def __init__(self, check_id: str, message: str) -> None:
        self.check_id = check_id
        self.message = message
        super().__init__(f"{check_id}: {message}")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_public_api_text() -> str:
    return (
        json.dumps(
            build_public_api_manifest(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def final_manifest_text(manifest: dict) -> str:
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def build_final_manifest(root: Path) -> dict:
    root = root.resolve()
    payload = {
        "artifact_format_version": "1.0.0",
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "final_release_gate_version": FINAL_RELEASE_GATE_VERSION,
        "rc_merge_sha": RC_MERGE_SHA,
        "final_release": True,
        "rc_not_final_v1": False,
        "public_api_artifact": {
            "path": FINAL_PUBLIC_API_ARTIFACT,
            "sha256": _sha256_file(root / FINAL_PUBLIC_API_ARTIFACT),
        },
        "historical_rc_artifacts": {
            RC_PUBLIC_API_ARTIFACT: _sha256_file(root / RC_PUBLIC_API_ARTIFACT),
            RC_MANIFEST_ARTIFACT: _sha256_file(root / RC_MANIFEST_ARTIFACT),
        },
        "benchmark_artifacts": {
            rel: _sha256_file(root / rel)
            for rel in REQUIRED_BENCHMARK_ARTIFACTS
        },
        "required_release_docs": list(REQUIRED_RELEASE_DOCS),
        "gate_evidence": {
            gate: list(paths)
            for gate, paths in GATE_EVIDENCE.items()
        },
        "reference_workflows": {
            workflow: list(paths)
            for workflow, paths in REFERENCE_WORKFLOW_EVIDENCE.items()
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "manifest_id": "omphalos-final-manifest:" + hashlib.sha256(encoded).hexdigest(),
        **payload,
    }


def _require_files(
    root: Path,
    mapping: dict[str, tuple[str, ...]],
    *,
    check_id: str,
) -> int:
    missing: list[str] = []
    count = 0
    for paths in mapping.values():
        for rel in paths:
            count += 1
            if not (root / rel).is_file():
                missing.append(rel)
    if missing:
        raise FinalReleaseGateFailure(check_id, f"missing evidence files: {sorted(set(missing))}")
    return count


def run_final_release_gate(root: Path) -> dict:
    root = root.resolve()
    checks: list[dict[str, str]] = []

    def pass_check(check_id: str, detail: str) -> None:
        checks.append({"id": check_id, "status": "pass", "detail": detail})

    if PACKAGE_VERSION != FINAL_PACKAGE_VERSION:
        raise FinalReleaseGateFailure(
            "package_version",
            f"facade={PACKAGE_VERSION} expected={FINAL_PACKAGE_VERSION}",
        )
    if PUBLIC_API_VERSION != "1.0":
        raise FinalReleaseGateFailure(
            "public_api_version",
            f"public API={PUBLIC_API_VERSION} expected=1.0",
        )

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["version"] != FINAL_PACKAGE_VERSION:
        raise FinalReleaseGateFailure(
            "package_version",
            f"pyproject={pyproject['project']['version']} expected={FINAL_PACKAGE_VERSION}",
        )
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    for required in ("src/crawler", "src/ai_web_research", "src/omphalos"):
        if required not in packages:
            raise FinalReleaseGateFailure("wheel_packages", f"missing {required}")
    if pyproject["project"]["scripts"].get("omphalos") != "omphalos.cli:main":
        raise FinalReleaseGateFailure("console_script", "omphalos CLI entry point missing")
    pass_check("package_version", FINAL_PACKAGE_VERSION)
    pass_check("wheel_packages", "crawler + implementation + frozen facade")
    pass_check("console_script", "omphalos.cli:main")

    final_api_path = root / FINAL_PUBLIC_API_ARTIFACT
    if not final_api_path.is_file():
        raise FinalReleaseGateFailure("public_api_manifest", "final public API artifact missing")
    actual_final_api_text = final_api_path.read_text(encoding="utf-8")
    expected_final_api_text = _canonical_public_api_text()
    if actual_final_api_text != expected_final_api_text:
        raise FinalReleaseGateFailure(
            "public_api_manifest",
            "final public API artifact does not exactly regenerate",
        )
    final_api = json.loads(actual_final_api_text)
    if final_api["package_version"] != FINAL_PACKAGE_VERSION:
        raise FinalReleaseGateFailure("public_api_manifest", "final package version mismatch")
    forbidden = _find_forbidden_fields(final_api)
    if forbidden:
        raise FinalReleaseGateFailure(
            "public_api_forbidden_fields",
            f"forbidden serialized fields: {forbidden}",
        )
    pass_check("public_api_manifest", f"{len(final_api['contracts'])} contracts")
    pass_check("public_api_forbidden_fields", "none")

    rc_api_path = root / RC_PUBLIC_API_ARTIFACT
    rc_manifest_path = root / RC_MANIFEST_ARTIFACT
    if not rc_api_path.is_file() or not rc_manifest_path.is_file():
        raise FinalReleaseGateFailure("historical_rc_artifacts", "historical RC artifacts missing")
    if _sha256_file(rc_api_path) != RC_PUBLIC_API_SHA256:
        raise FinalReleaseGateFailure("historical_rc_artifacts", "RC public API artifact changed")
    if _sha256_file(rc_manifest_path) != RC_MANIFEST_SHA256:
        raise FinalReleaseGateFailure("historical_rc_artifacts", "RC manifest artifact changed")
    rc_api = json.loads(rc_api_path.read_text(encoding="utf-8"))
    rc_manifest = json.loads(rc_manifest_path.read_text(encoding="utf-8"))
    if rc_api["package_version"] != RC_PACKAGE_VERSION:
        raise FinalReleaseGateFailure("historical_rc_artifacts", "RC API version identity changed")
    if rc_manifest.get("rc_not_final_v1") is not True:
        raise FinalReleaseGateFailure("historical_rc_artifacts", "RC finality marker changed")
    if final_api["contracts"] != rc_api["contracts"]:
        raise FinalReleaseGateFailure(
            "api_freeze",
            "public contract descriptors changed between RC and final",
        )
    if final_api["public_api_version"] != rc_api["public_api_version"]:
        raise FinalReleaseGateFailure(
            "api_freeze",
            "public API version changed between RC and final",
        )
    pass_check("historical_rc_artifacts", "byte-identical RC API + manifest")
    pass_check("api_freeze", "RC and final contract descriptors identical")

    missing_docs = [rel for rel in REQUIRED_RELEASE_DOCS if not (root / rel).is_file()]
    if missing_docs:
        raise FinalReleaseGateFailure("release_docs", f"missing {missing_docs}")
    pass_check("release_docs", f"{len(REQUIRED_RELEASE_DOCS)} files")

    missing_benchmarks = [
        rel for rel in REQUIRED_BENCHMARK_ARTIFACTS if not (root / rel).is_file()
    ]
    if missing_benchmarks:
        raise FinalReleaseGateFailure(
            "benchmark_artifacts",
            f"missing {missing_benchmarks}",
        )
    pass_check("benchmark_artifacts", f"{len(REQUIRED_BENCHMARK_ARTIFACTS)} files")

    if tuple(GATE_EVIDENCE) != (
        "G1_METHOD",
        "G2_PROVIDER",
        "G3_REPLACEABILITY",
        "G4_PLANNER",
        "G5_POLICY",
        "G6_EVIDENCE",
        "G7_GAP_STOP",
        "G8_RECEIPT",
        "G9_EVALUATION",
    ):
        raise FinalReleaseGateFailure("g1_g9_map", "canonical G1-G9 map is incomplete")
    gate_file_count = _require_files(
        root,
        GATE_EVIDENCE,
        check_id="g1_g9_map",
    )
    pass_check("g1_g9_map", f"9 gates / {gate_file_count} behavior test files")

    if set(REFERENCE_WORKFLOW_EVIDENCE) != {
        "general_web",
        "current_x_web",
        "academic_npl",
        "patent_prior_art",
    }:
        raise FinalReleaseGateFailure(
            "reference_workflows",
            "four canonical reference workflow mappings are incomplete",
        )
    workflow_file_count = _require_files(
        root,
        REFERENCE_WORKFLOW_EVIDENCE,
        check_id="reference_workflows",
    )
    pass_check(
        "reference_workflows",
        f"4 workflows / {workflow_file_count} E2E/reference test files",
    )

    final_manifest_path = root / FINAL_MANIFEST_ARTIFACT
    if not final_manifest_path.is_file():
        raise FinalReleaseGateFailure("final_manifest", "final manifest missing")
    expected_manifest = final_manifest_text(build_final_manifest(root))
    if final_manifest_path.read_text(encoding="utf-8") != expected_manifest:
        raise FinalReleaseGateFailure(
            "final_manifest",
            "final manifest does not exactly regenerate",
        )
    pass_check("final_manifest", "content-addressed and reproducible")

    secret_hits: list[dict[str, str]] = []
    for rel in ("src", "scripts", ".github/workflows", "release"):
        secret_hits.extend(scan_literal_secrets(root / rel))
    if secret_hits:
        raise FinalReleaseGateFailure(
            "literal_secret_scan",
            json.dumps(secret_hits, sort_keys=True),
        )
    pass_check("literal_secret_scan", "no literal credential assignments/raw tokens")

    final_workflow = root / ".github/workflows/omphalos-v1-final.yml"
    if not final_workflow.is_file():
        raise FinalReleaseGateFailure("final_workflow", "final workflow missing")
    pass_check("final_workflow", str(final_workflow.relative_to(root)))

    return {
        "status": "pass",
        "final_release_gate_version": FINAL_RELEASE_GATE_VERSION,
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "rc_merge_sha": RC_MERGE_SHA,
        "checks": checks,
    }
