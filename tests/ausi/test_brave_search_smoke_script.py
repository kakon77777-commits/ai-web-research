import os
import subprocess
import sys


def test_smoke_script_skips_cleanly_without_credential():
    env = dict(os.environ)
    env.pop('BRAVE_SEARCH_API_KEY', None)
    env['PYTHONPATH'] = 'src'
    proc = subprocess.run(
        [sys.executable, 'scripts/verify_brave_search_provider.py'],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == 'SKIPPED_NO_CREDENTIAL'
    assert 'secret' not in proc.stdout.lower()
