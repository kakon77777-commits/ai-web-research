from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tomllib

from .api import build_public_api_manifest
from .version import PACKAGE_VERSION, PUBLIC_API_VERSION


RELEASE_GATE_VERSION = "0.9.0"
RC_BASE_MASTER_SHA = "ee490addeaac29efa7831df728950c0cad68f07e"

REQUIRED_RELEASE_DOCS = (
    "docs/QUICKSTART.md",
    "docs/release/API_STABILITY_AND_MIGRATION_v1.md",
    "docs/release/SECURITY_AND_CREDENTIALS_v1.md",
    "docs/release/REFERENCE_WORKFLOWS_v1.md",
    "docs/release/RELEASE_CANDIDATE_v1.0.0rc1.md",
)

REQUIRED_BENCHMARK_ARTIFACTS = (
    "benchmarks/omphalos-v0.8-reference-suite.json",
    "benchmarks/artifacts/omphalos-v0.8-reference-report.json",
    "benchmarks/artifacts/omphalos-v0.8-reference-manifest.json",
)

_PUBLIC_API_ARTIFACT = "release/omphalos-v1.0.0rc1-public-api.json"

_LITERAL_SECRET = re.compile(
    r"""(?ix)
    \b(api_key|access_token|refresh_token|client_secret|private_key|password)
    \s*=\s*
    (["'])(?:(?!\2).)+\2
    """
)

_RAW_SECRET_PATTERNS = (
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
)

_FORBIDDEN_SERIALIZED_FIELDS = {
    "chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
    "credential_value",
    "raw_credential",
}


class ReleaseGateFailure(RuntimeError):
    def __init__(self, check_id: str, message: str) -> None:
        self.check_id = check_id
        self.message = message
        super().__init__(f"{check_id}: {message}")


def _walk_files(root: Path):
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() in {".py", ".toml", ".yaml", ".yml", ".json"}
            and "__pycache__" not in path.parts
        ):
            yield path


def scan_literal_secrets(root: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in _walk_files(root) or ():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _LITERAL_SECRET.search(text):
            hits.append(
                {
                    "path": str(path),
                    "kind": "literal_secret_assignment",
                }
            )
        for kind, pattern in _RAW_SECRET_PATTERNS:
            if pattern.search(text):
                hits.append({"path": str(path), "kind": kind})
    return hits


def _find_forbidden_fields(value, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_SERIALIZED_FIELDS:
                hits.append(f"{path}.{key}")
            hits.extend(_find_forbidden_fields(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            hits.extend(_find_forbidden_fields(nested, f"{path}[{index}]"))
    return hits


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


def run_release_gate(root: Path) -> dict:
    root = root.resolve()
    checks: list[dict[str, str]] = []

    def pass_check(check_id: str, detail: str) -> None:
        checks.append({"id": check_id, "status": "pass", "detail": detail})

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["version"] != PACKAGE_VERSION:
        raise ReleaseGateFailure(
            "package_version",
            f"pyproject={pyproject['project']['version']} facade={PACKAGE_VERSION}",
        )
    pass_check("package_version", PACKAGE_VERSION)

    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    for required in ("src/ai_web_research", "src/omphalos"):
        if required not in packages:
            raise ReleaseGateFailure("wheel_packages", f"missing {required}")
    if pyproject["project"]["scripts"].get("omphalos") != "omphalos.cli:main":
        raise ReleaseGateFailure("console_script", "omphalos CLI entry point missing")
    pass_check("wheel_packages", "implementation + facade")
    pass_check("console_script", "omphalos.cli:main")

    public_api_path = root / _PUBLIC_API_ARTIFACT
    actual_public_text = public_api_path.read_text(encoding="utf-8")
    expected_public_text = _canonical_public_api_text()
    if actual_public_text != expected_public_text:
        raise ReleaseGateFailure(
            "public_api_manifest",
            "repository artifact does not exactly regenerate",
        )
    public_data = json.loads(actual_public_text)
    if public_data["public_api_version"] != PUBLIC_API_VERSION:
        raise ReleaseGateFailure("public_api_version", "manifest/API version mismatch")
    forbidden = _find_forbidden_fields(public_data)
    if forbidden:
        raise ReleaseGateFailure(
            "public_api_forbidden_fields",
            f"forbidden serialized fields: {forbidden}",
        )
    pass_check("public_api_manifest", f"{len(public_data['contracts'])} contracts")
    pass_check("public_api_forbidden_fields", "none")

    missing_docs = [rel for rel in REQUIRED_RELEASE_DOCS if not (root / rel).is_file()]
    if missing_docs:
        raise ReleaseGateFailure("release_docs", f"missing {missing_docs}")
    pass_check("release_docs", f"{len(REQUIRED_RELEASE_DOCS)} files")

    missing_benchmarks = [
        rel for rel in REQUIRED_BENCHMARK_ARTIFACTS if not (root / rel).is_file()
    ]
    if missing_benchmarks:
        raise ReleaseGateFailure(
            "benchmark_artifacts", f"missing {missing_benchmarks}"
        )
    pass_check("benchmark_artifacts", f"{len(REQUIRED_BENCHMARK_ARTIFACTS)} files")

    rc_manifest_path = root / "release/omphalos-v1.0.0rc1-manifest.json"
    expected_rc_manifest = rc_manifest_text(build_rc_manifest(root))
    if not rc_manifest_path.is_file():
        raise ReleaseGateFailure("rc_manifest", "RC manifest file missing")
    if rc_manifest_path.read_text(encoding="utf-8") != expected_rc_manifest:
        raise ReleaseGateFailure(
            "rc_manifest",
            "repository RC manifest does not exactly regenerate",
        )
    pass_check("rc_manifest", "content-addressed and reproducible")

    secret_hits = []
    for rel in ("src", "scripts"):
        secret_hits.extend(scan_literal_secrets(root / rel))
    if secret_hits:
        raise ReleaseGateFailure("literal_secret_scan", json.dumps(secret_hits))
    pass_check("literal_secret_scan", "no literal credential assignments/raw tokens")

    workflow = root / ".github/workflows/omphalos-rc.yml"
    if not workflow.is_file():
        raise ReleaseGateFailure("rc_workflow", "workflow file missing")
    pass_check("rc_workflow", str(workflow.relative_to(root)))

    return {
        "status": "pass",
        "release_gate_version": RELEASE_GATE_VERSION,
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "checks": checks,
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rc_manifest_text(manifest: dict) -> str:
    return json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def build_rc_manifest(root: Path) -> dict:
    root = root.resolve()
    payload = {
        "artifact_format_version": "0.9.0",
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "release_gate_version": RELEASE_GATE_VERSION,
        "base_master_sha": RC_BASE_MASTER_SHA,
        "rc_not_final_v1": True,
        "public_api_artifact": {
            "path": _PUBLIC_API_ARTIFACT,
            "sha256": _sha256_file(root / _PUBLIC_API_ARTIFACT),
        },
        "benchmark_artifacts": {
            rel: _sha256_file(root / rel)
            for rel in REQUIRED_BENCHMARK_ARTIFACTS
        },
        "required_release_docs": list(REQUIRED_RELEASE_DOCS),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "manifest_id": "omphalos-rc-manifest:" + hashlib.sha256(encoded).hexdigest(),
        **payload,
    }
