import json
from pathlib import Path
import subprocess
import sys

from omphalos.final_release import (
    GATE_EVIDENCE,
    REFERENCE_WORKFLOW_EVIDENCE,
    REQUIRED_RELEASE_DOCS,
    build_final_manifest,
    run_final_release_gate,
)
from omphalos.release import scan_literal_secrets


def test_final_release_gate_passes_current_tree_and_script_json():
    result = run_final_release_gate(Path('.'))
    assert result['status'] == 'pass'
    assert len(result['checks']) == 14
    assert result['package_version'] == '1.0.0'
    proc = subprocess.run([sys.executable, 'scripts/omphalos_final_release_gate.py', '--json'], text=True, capture_output=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)['status'] == 'pass'


def test_final_manifest_exactly_regenerates_and_maps_all_release_gates():
    stored = json.loads(Path('release/omphalos-v1.0.0-final-manifest.json').read_text(encoding='utf-8'))
    assert build_final_manifest(Path('.')) == stored
    assert len(GATE_EVIDENCE) == 9
    assert set(REFERENCE_WORKFLOW_EVIDENCE) == {'general_web', 'current_x_web', 'academic_npl', 'patent_prior_art'}


def test_final_secret_scan_and_full_repo_ci_contract():
    assert scan_literal_secrets(Path('src')) == []
    assert scan_literal_secrets(Path('scripts')) == []
    assert all((Path('.') / rel).is_file() for rel in REQUIRED_RELEASE_DOCS)
    workflow = Path('.github/workflows/omphalos-v1-final.yml').read_text(encoding='utf-8')
    for token in ['python -m pytest -q', 'python -m compileall', 'omphalos_final_release_gate.py', 'Reproducible final build A', 'Reproducible final build B and compare', 'pip install --no-deps', 'omphalos version', 'omphalos doctor --json']:
        assert token in workflow
