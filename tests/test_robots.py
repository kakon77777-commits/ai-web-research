import httpx
import pytest

from crawler.robots import RobotsCache

ROBOTS_TXT = """
User-agent: *
Disallow: /private/
Crawl-delay: 2
"""


def _make_client(robots_body: str = ROBOTS_TXT, status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(status_code, text=robots_body)
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_allows_unrestricted_path():
    async with _make_client() as client:
        cache = RobotsCache(client, user_agent="TestBot/1.0")
        assert await cache.is_allowed("https://example.com/public/page") is True


async def test_disallows_restricted_path():
    async with _make_client() as client:
        cache = RobotsCache(client, user_agent="TestBot/1.0")
        assert await cache.is_allowed("https://example.com/private/secret") is False


async def test_reads_crawl_delay():
    async with _make_client() as client:
        cache = RobotsCache(client, user_agent="TestBot/1.0")
        delay = await cache.crawl_delay("https://example.com/public/page")
        assert delay == 2.0


async def test_missing_robots_txt_allows_everything():
    async with _make_client(status_code=404) as client:
        cache = RobotsCache(client, user_agent="TestBot/1.0")
        assert await cache.is_allowed("https://example.com/anything") is True


async def test_caches_parser_per_domain():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=ROBOTS_TXT)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        cache = RobotsCache(client, user_agent="TestBot/1.0")
        await cache.is_allowed("https://example.com/a")
        await cache.is_allowed("https://example.com/b")
        assert call_count == 1
