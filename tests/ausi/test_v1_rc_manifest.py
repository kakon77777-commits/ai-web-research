import hashlib
import json
from pathlib import Path

MANIFEST = Path('release/omphalos-v1.0.0rc1-manifest.json')
API = Path('release/omphalos-v1.0.0rc1-public-api.json')


def test_historical_rc_artifacts_remain_byte_identical_after_final_promotion():
    assert hashlib.sha256(API.read_bytes()).hexdigest() == '7e46a963e19100c1feac9525ee221b82b98f4dad78a85e25bc55d8a2665763a9'
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == 'cc5440800ae16ce93a2b2592d8343d77f9811e377287ed1e1c8eadc6bb824c2a'
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert data['package_version'] == '1.0.0rc1'
    assert data['public_api_version'] == '1.0'
    assert data['release_gate_version'] == '0.9.0'
    assert data['base_master_sha'] == 'ee490addeaac29efa7831df728950c0cad68f07e'
    assert data['rc_not_final_v1'] is True
