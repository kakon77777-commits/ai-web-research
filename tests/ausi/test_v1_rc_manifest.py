import json
from pathlib import Path
from omphalos.release import RC_BASE_MASTER_SHA, build_rc_manifest, rc_manifest_text

MANIFEST = Path('release/omphalos-v1.0.0rc1-manifest.json')


def test_rc_manifest_is_deterministic_content_addressed_and_not_final_v1():
    generated = build_rc_manifest(Path('.'))
    assert generated == json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert MANIFEST.read_text(encoding='utf-8') == rc_manifest_text(generated)
    assert generated['base_master_sha'] == RC_BASE_MASTER_SHA == 'ee490addeaac29efa7831df728950c0cad68f07e'
    assert generated['package_version'] == '1.0.0rc1'
    assert generated['public_api_version'] == '1.0'
    assert generated['release_gate_version'] == '0.9.0'
    assert generated['rc_not_final_v1'] is True
    assert generated['manifest_id'].startswith('omphalos-rc-manifest:')
    assert len(generated['manifest_id'].split(':', 1)[1]) == 64
    assert generated['public_api_artifact']['sha256']
    assert len(generated['benchmark_artifacts']) == 3
