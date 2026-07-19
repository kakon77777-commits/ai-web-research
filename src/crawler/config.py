"""Load config/crawler.yaml into typed config objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CrawlerConfig:
    user_agent: str
    obey_robots_txt: bool
    max_depth: int
    max_pages_per_domain: int
    max_concurrency_global: int
    max_concurrency_per_domain: int
    request_timeout_seconds: float
    retry_count: int
    save_raw: bool
    save_screenshot_on_error: bool


@dataclass
class SecurityConfig:
    block_private_networks: bool
    allow_file_scheme: bool
    allow_localhost: bool
    prompt_injection_is_untrusted: bool


@dataclass
class StorageConfig:
    raw_dir: Path
    parsed_dir: Path
    db_path: Path


@dataclass
class AppConfig:
    crawler: CrawlerConfig
    security: SecurityConfig
    storage: StorageConfig


def load_config(path: Path) -> AppConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    c = data["crawler"]
    s = data["security"]
    st = data["storage"]
    return AppConfig(
        crawler=CrawlerConfig(
            user_agent=c["user_agent"],
            obey_robots_txt=bool(c.get("obey_robots_txt", True)),
            max_depth=int(c.get("max_depth", 3)),
            max_pages_per_domain=int(c.get("max_pages_per_domain", 50)),
            max_concurrency_global=int(c.get("max_concurrency_global", 4)),
            max_concurrency_per_domain=int(c.get("max_concurrency_per_domain", 2)),
            request_timeout_seconds=float(c.get("request_timeout_seconds", 20)),
            retry_count=int(c.get("retry_count", 3)),
            save_raw=bool(c.get("save_raw", True)),
            save_screenshot_on_error=bool(c.get("save_screenshot_on_error", False)),
        ),
        security=SecurityConfig(
            block_private_networks=bool(s.get("block_private_networks", True)),
            allow_file_scheme=bool(s.get("allow_file_scheme", False)),
            allow_localhost=bool(s.get("allow_localhost", False)),
            prompt_injection_is_untrusted=bool(s.get("prompt_injection_is_untrusted", True)),
        ),
        storage=StorageConfig(
            raw_dir=Path(st.get("raw_dir", "storage/raw")),
            parsed_dir=Path(st.get("parsed_dir", "storage/parsed")),
            db_path=Path(st.get("db_path", "storage/metadata/crawl.db")),
        ),
    )
