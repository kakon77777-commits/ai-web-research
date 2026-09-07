import json
import subprocess
import sys
import tomllib


def run_cli(*args):
    return subprocess.run([sys.executable, '-m', 'omphalos', *args], text=True, capture_output=True, check=False)


def test_rc_package_metadata_and_console_entry_are_frozen():
    data = tomllib.loads(open('pyproject.toml', 'rb').read().decode())
    assert data['project']['version'] == '1.0.0rc1'
    assert data['project']['scripts']['omphalos'] == 'omphalos.cli:main'
    packages = data['tool']['hatch']['build']['targets']['wheel']['packages']
    assert 'src/ai_web_research' in packages and 'src/omphalos' in packages


def test_offline_cli_version_api_and_doctor():
    version = run_cli('version')
    assert version.returncode == 0 and '1.0.0rc1' in version.stdout and 'public API 1.0' in version.stdout
    api = run_cli('api', '--json')
    assert api.returncode == 0 and json.loads(api.stdout)['public_api_version'] == '1.0'
    doctor = run_cli('doctor', '--json')
    payload = json.loads(doctor.stdout)
    assert doctor.returncode == 0 and payload['status'] == 'ok'
    assert payload['network_required'] is False and payload['credential_required'] is False
