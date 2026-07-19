"""robots.txt fetching and permission checks, cached per-domain."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import httpx

from .normalize import registered_domain


class RobotsCache:
    """Fetches and caches robots.txt rules per domain.

    A fetch failure (no robots.txt, network error, non-200) is treated as
    "no restrictions" per standard crawler convention.
    """

    def __init__(self, client: httpx.AsyncClient, user_agent: str, timeout: float = 10.0):
        self._client = client
        self._user_agent = user_agent
        self._timeout = timeout
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def _get_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = registered_domain(url)
        if domain in self._parsers:
            return self._parsers[domain]

        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)

        try:
            resp = await self._client.get(
                robots_url,
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
            )
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            else:
                parser.parse([])
        except httpx.HTTPError:
            parser.parse([])

        self._parsers[domain] = parser
        return parser

    async def is_allowed(self, url: str) -> bool:
        parser = await self._get_parser(url)
        return parser.can_fetch(self._user_agent, url)

    async def crawl_delay(self, url: str) -> float | None:
        parser = await self._get_parser(url)
        delay = parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None
