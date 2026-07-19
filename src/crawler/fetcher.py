"""Downloader: wraps Crawl4AI's AsyncWebCrawler with our own retry/backoff.

T_k = min(T_max, T_0 * 2^k), k = consecutive failure count (doc section 6.2).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

_MAX_BACKOFF_SECONDS = 30.0
_BASE_BACKOFF_SECONDS = 1.0


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    success: bool
    html: str
    markdown: str
    content_type: str
    error_message: str | None


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float,
        retry_count: int,
        save_screenshot_on_error: bool = False,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.save_screenshot_on_error = save_screenshot_on_error
        self._browser_config = BrowserConfig(headless=True, user_agent=user_agent)
        self._crawler: AsyncWebCrawler | None = None

    async def __aenter__(self) -> "Fetcher":
        self._crawler = AsyncWebCrawler(config=self._browser_config)
        await self._crawler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._crawler is not None:
            await self._crawler.__aexit__(exc_type, exc, tb)

    async def fetch(self, url: str) -> FetchResult:
        assert self._crawler is not None, "Fetcher must be used as an async context manager"

        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=int(self.timeout_seconds * 1000),
            screenshot=self.save_screenshot_on_error,
        )

        last_error: str | None = None
        for attempt in range(self.retry_count + 1):
            try:
                result = await self._crawler.arun(url=url, config=run_config)
                if result.success:
                    content_type = "text/html"
                    if result.response_headers:
                        raw_ct = result.response_headers.get("content-type") or result.response_headers.get("Content-Type")
                        if raw_ct:
                            content_type = raw_ct.split(";")[0].strip()
                    return FetchResult(
                        url=url,
                        final_url=result.redirected_url or result.url,
                        status_code=result.status_code,
                        success=True,
                        html=result.html or "",
                        markdown=str(result.markdown) if result.markdown else "",
                        content_type=content_type,
                        error_message=None,
                    )
                last_error = result.error_message
            except Exception as exc:  # noqa: BLE001 - network/browser layer raises many types
                last_error = str(exc)

            if attempt < self.retry_count:
                backoff = min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * (2 ** attempt))
                await asyncio.sleep(backoff)

        return FetchResult(
            url=url,
            final_url=url,
            status_code=None,
            success=False,
            html="",
            markdown="",
            content_type="",
            error_message=last_error,
        )
