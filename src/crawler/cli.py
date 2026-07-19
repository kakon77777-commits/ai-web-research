"""CLI entry point: `crawler crawl <url> [--config PATH] [--max-pages N] [--max-depth N]`"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import load_config
from .run import crawl_site

DEFAULT_CONFIG_PATH = Path("config/crawler.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawler", description="Stage 1 AI crawler")
    parser.add_argument("command", choices=["crawl"])
    parser.add_argument("url", help="Seed URL to crawl")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
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

    stats = asyncio.run(crawl_site(args.url, config))

    print(
        f"fetched={stats.fetched} unchanged={stats.unchanged} "
        f"skipped_robots={stats.skipped_robots} skipped_ssrf={stats.skipped_ssrf} "
        f"failed={stats.failed}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
