import json
from pathlib import Path
import subprocess
import sys
from omphalos.release import REQUIRED_RELEASE_DOCS, run_release_gate, scan_literal_secrets


def test_release_gate_passes_current_rc_tree_and_script_json():
    result = run_release_gate(Path('.'))
    assert result['status'] == 'pass'
    assert len(result['checks']) == 10
    proc = subprocess.run([sys.executable, 'scripts/omphalos_release_gate.py', '--json'], text=True, capture_output=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)['status'] == 'pass'


def test_secret_scan_and_full_repo_ci_contract():
    assert scan_literal_secrets(Path('src')) == []
    assert scan_literal_secrets(Path('scripts')) == []
    assert all((Path('.') / rel).is_file() for rel in REQUIRED_RELEASE_DOCS)
    workflow = Path('.github/workflows/omphalos-rc.yml').read_text(encoding='utf-8')
    for token in ['pytest -q', 'python -m compileall', 'python -m build', 'pip install --no-deps', 'omphalos version', 'omphalos doctor --json']:
        assert token in workflow
