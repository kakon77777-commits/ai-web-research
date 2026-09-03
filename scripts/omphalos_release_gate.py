from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from omphalos.release import ReleaseGateFailure, run_release_gate


def main() -> int:
    parser = argparse.ArgumentParser(prog="omphalos-release-gate")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        result = run_release_gate(Path("."))
    except ReleaseGateFailure as exc:
        payload = {
            "status": "fail",
            "check_id": exc.check_id,
            "message": exc.message,
        }
        if args.as_json:
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        else:
            print(f"FAIL {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(
            f"PASS Omphalos {result['package_version']} "
            f"public API {result['public_api_version']}"
        )
        for check in result["checks"]:
            print(f"PASS {check['id']}: {check['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
