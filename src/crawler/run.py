"""Orchestrator: discover -> fetch -> parse -> dedup -> store, bounded by
domain scope, max_depth and max_pages_per_domain.

Matches the MVP 階段一/階段二 closed loop from the project doc:
Discover -> Fetch -> Parse -> Store -> Verify -> Update.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

import httpx

from .config import AppConfig
from .extract import extract_links, extract_metadata
from .fetcher import Fetcher
from .frontier import UrlFrontier
from .normalize import registered_domain
from .robots import RobotsCache
from .security import SSRFBlockedError, SSRFGuard
from .sitemap import discover_sitemap_urls, fetch_sitemap_page_urls
from .store import PageRecord, PageStore, document_id_for, sha256_hex, write_parsed, write_raw

logger = logging.getLogger("crawler")


@dataclass
class CrawlStats:
    fetched: int = 0
    skipped_robots: int = 0
    skipped_ssrf: int = 0
    unchanged: int = 0
    failed: int = 0


async def crawl_site(seed_url: str, config: AppConfig) -> CrawlStats:
    stats = CrawlStats()
    domain = registered_domain(seed_url)

    store = PageStore(config.storage.db_path)
    ssrf_guard = SSRFGuard(
        block_private_networks=config.security.block_private_networks,
        allow_localhost=config.security.allow_localhost,
        allow_file_scheme=config.security.allow_file_scheme,
    )

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            robots = RobotsCache(
                client, config.crawler.user_agent, timeout=config.crawler.request_timeout_seconds
            )

            frontier = UrlFrontier(
                seed_url=seed_url,
                max_depth=config.crawler.max_depth,
                max_pages=config.crawler.max_pages_per_domain,
            )

            try:
                sitemap_candidates = await discover_sitemap_urls(
                    client, seed_url, config.crawler.user_agent
                )
                for sitemap_url in sitemap_candidates:
                    page_urls = await fetch_sitemap_page_urls(
                        client, sitemap_url, config.crawler.user_agent
                    )
                    frontier.add_many(page_urls, depth=1)
            except httpx.HTTPError as exc:
                logger.warning("sitemap discovery failed: %s", exc)

            semaphore = asyncio.Semaphore(config.crawler.max_concurrency_per_domain)

            async with Fetcher(
                user_agent=config.crawler.user_agent,
                timeout_seconds=config.crawler.request_timeout_seconds,
                retry_count=config.crawler.retry_count,
                save_screenshot_on_error=config.crawler.save_screenshot_on_error,
            ) as fetcher:

                async def process_one(entry_url: str, depth: int) -> None:
                    async with semaphore:
                        if config.crawler.obey_robots_txt:
                            allowed = await robots.is_allowed(entry_url)
                            if not allowed:
                                stats.skipped_robots += 1
                                logger.info("robots.txt disallows: %s", entry_url)
                                return

                        try:
                            await ssrf_guard.check(entry_url)
                        except SSRFBlockedError as exc:
                            stats.skipped_ssrf += 1
                            logger.warning("SSRF guard blocked: %s", exc)
                            return

                        result = await fetcher.fetch(entry_url)
                        if not result.success:
                            stats.failed += 1
                            logger.warning(
                                "fetch failed for %s: %s", entry_url, result.error_message
                            )
                            return

                        content_hash = sha256_hex(result.html)
                        previous_hash = store.previous_hash(entry_url)
                        unchanged = previous_hash == content_hash

                        meta = extract_metadata(result.html, result.final_url)
                        doc_id = document_id_for(entry_url)

                        raw_path = None
                        parsed_path = None
                        if not unchanged:
                            if config.crawler.save_raw:
                                raw_path = str(
                                    write_raw(config.storage.raw_dir, domain, doc_id, result.html)
                                )
                            parsed_path = str(
                                write_parsed(
                                    config.storage.parsed_dir, domain, doc_id, result.markdown
                                )
                            )

                        record = PageRecord(
                            url=entry_url,
                            canonical_url=meta.canonical_url,
                            domain=domain,
                            fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                            published_at=meta.published_at,
                            status_code=result.status_code,
                            content_type=result.content_type or "text/html",
                            raw_path=raw_path,
                            markdown_path=parsed_path,
                            content_hash=content_hash,
                            language=meta.language,
                            title=meta.title,
                            author=meta.author,
                            license_hint=None,
                            robots_allowed=True,
                        )
                        store.upsert(record, unchanged=unchanged)

                        if unchanged:
                            stats.unchanged += 1
                        else:
                            stats.fetched += 1

                        if depth < config.crawler.max_depth:
                            links = extract_links(result.html, result.final_url)
                            frontier.add_many(links, depth=depth + 1)

                while True:
                    batch = []
                    while frontier.has_next() and len(batch) < config.crawler.max_concurrency_global:
                        entry = frontier.pop()
                        batch.append(asyncio.create_task(process_one(entry.url, entry.depth)))
                    if not batch:
                        break
                    await asyncio.gather(*batch)
    finally:
        store.close()

    return stats
