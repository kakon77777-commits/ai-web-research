import json
from pathlib import Path

import omphalos


FINAL_API = Path("release/omphalos-v1.0.0-public-api.json")
FINAL_MANIFEST = Path("release/omphalos-v1.0.0-final-manifest.json")
RC_MANIFEST = Path("release/omphalos-v1.0.0rc1-manifest.json")
RC_API = Path("release/omphalos-v1.0.0rc1-public-api.json")


def test_final_package_identity_is_1_0_0_with_public_api_1_0():
    assert omphalos.__version__ == "1.0.0"
    assert omphalos.PUBLIC_API_VERSION == "1.0"


def test_final_release_artifacts_exist_and_identify_final_v1():
    assert FINAL_API.is_file()
    assert FINAL_MANIFEST.is_file()
    api = json.loads(FINAL_API.read_text(encoding="utf-8"))
    manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))
    assert api["package_version"] == "1.0.0"
    assert api["public_api_version"] == "1.0"
    assert manifest["package_version"] == "1.0.0"
    assert manifest["public_api_version"] == "1.0"
    assert manifest["final_release"] is True
    assert manifest["rc_not_final_v1"] is False
    assert manifest["rc_merge_sha"] == "c291567bcc4ec59bacdc90036819e0db264a2f23"


def test_rc_artifacts_remain_historical_and_are_not_rewritten_as_final():
    assert RC_API.is_file()
    assert RC_MANIFEST.is_file()
    rc_api = json.loads(RC_API.read_text(encoding="utf-8"))
    rc_manifest = json.loads(RC_MANIFEST.read_text(encoding="utf-8"))
    assert rc_api["package_version"] == "1.0.0rc1"
    assert rc_manifest["package_version"] == "1.0.0rc1"
    assert rc_manifest["rc_not_final_v1"] is True
