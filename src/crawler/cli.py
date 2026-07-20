"""CLI entry point:
`crawler crawl <url> [--config PATH] [--max-pages N] [--max-depth N]`
`crawler extract <url> [--config PATH] [--schema PATH]`
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .config import load_config
from .normalize import registered_domain
from .run import crawl_site
from .semantic_extract import extract_site

DEFAULT_CONFIG_PATH = Path("config/crawler.yaml")
DEFAULT_SCHEMA_PATH = Path("config/extraction_schema.example.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawler", description="Stage 1 AI crawler")
    parser.add_argument("command", choices=["crawl", "extract"])
    parser.add_argument("url", help="Seed URL to crawl, or a URL on the domain to run extraction for")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Discard any persisted frontier state for this domain and start over",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to a JSON Schema file describing fields to extract (used by 'extract')",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    if args.max_pages is not None:
        config.crawler.max_pages_per_domain = args.max_pages
    if args.max_depth is not None:
        config.crawler.max_depth = args.max_depth

    if args.command == "crawl":
        stats = asyncio.run(crawl_site(args.url, config, fresh=args.fresh))
        print(
            f"fetched={stats.fetched} unchanged={stats.unchanged} "
            f"skipped_robots={stats.skipped_robots} skipped_ssrf={stats.skipped_ssrf} "
            f"failed={stats.failed}"
        )
    else:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        domain = registered_domain(args.url)
        stats = asyncio.run(extract_site(domain, schema, config))
        print(
            f"extracted={stats.extracted} "
            f"skipped_missing_markdown={stats.skipped_missing_markdown} failed={stats.failed}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
