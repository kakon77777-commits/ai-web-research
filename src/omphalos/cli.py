from __future__ import annotations

import argparse
import json
from typing import Sequence

from .api import PUBLIC_EXPORTS, build_public_api_manifest
from .errors import ERROR_CATALOG
from .version import PACKAGE_VERSION, PUBLIC_API_VERSION


def _json_dump(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _doctor_payload() -> dict:
    manifest = build_public_api_manifest()
    return {
        "status": "ok",
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "public_contract_count": len(PUBLIC_EXPORTS),
        "error_code_count": len(ERROR_CATALOG),
        "network_required": False,
        "credential_required": False,
        "facade_package": "omphalos",
        "implementation_package": "ai_web_research",
        "manifest_contract_count": len(manifest["contracts"]),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omphalos",
        description="Omphalos / AUSI Runtime release-candidate utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="show package and public API versions")

    api_parser = subparsers.add_parser(
        "api", help="show the frozen public API manifest"
    )
    api_parser.add_argument("--json", action="store_true", dest="as_json")

    doctor_parser = subparsers.add_parser(
        "doctor", help="run offline package/public-contract checks"
    )
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "version":
        print(
            f"omphalos {PACKAGE_VERSION} "
            f"(public API {PUBLIC_API_VERSION})"
        )
        return 0

    if args.command == "api":
        manifest = build_public_api_manifest()
        if args.as_json:
            print(_json_dump(manifest))
        else:
            print(
                f"Omphalos public API {PUBLIC_API_VERSION} "
                f"({len(manifest['contracts'])} contracts)"
            )
            for name in sorted(manifest["contracts"]):
                print(name)
        return 0

    if args.command == "doctor":
        payload = _doctor_payload()
        if args.as_json:
            print(_json_dump(payload))
        else:
            print(
                "Omphalos doctor: "
                f"{payload['status']} "
                f"(package {PACKAGE_VERSION}, API {PUBLIC_API_VERSION})"
            )
        return 0

    raise AssertionError(f"unhandled command: {args.command}")
