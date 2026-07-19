"""Per-domain rate limiting: honors robots.txt Crawl-delay plus a configured
minimum interval, with random jitter to avoid lockstep request timing
(doc section 7: 每域名最大並行 + 隨機抖動 + 429 後退避).
"""

from __future__ import annotations

import asyncio
import random


class DomainRateLimiter:
    def __init__(self, jitter_seconds: float = 0.5):
        self.jitter_seconds = jitter_seconds
        self._next_allowed_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str, min_interval_seconds: float) -> None:
        loop = asyncio.get_event_loop()
        async with self._lock:
            now = loop.time()
            next_allowed = self._next_allowed_at.get(domain, now)
            start_at = max(now, next_allowed)
            jitter = random.uniform(0.0, self.jitter_seconds) if self.jitter_seconds > 0 else 0.0
            self._next_allowed_at[domain] = start_at + min_interval_seconds + jitter
            delay = start_at - now

        if delay > 0:
            await asyncio.sleep(delay)
