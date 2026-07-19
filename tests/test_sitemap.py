import httpx

from crawler.sitemap import discover_sitemap_urls, fetch_sitemap_page_urls

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
</sitemapindex>
"""

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>
"""


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text="Sitemap: https://example.com/sitemap_index.xml\n")
    if path == "/sitemap_index.xml":
        return httpx.Response(200, content=SITEMAP_INDEX.encode("utf-8"))
    if path == "/sitemap1.xml":
        return httpx.Response(200, content=URLSET.encode("utf-8"))
    return httpx.Response(404)


async def test_discover_sitemap_urls_from_robots_txt():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        urls = await discover_sitemap_urls(client, "https://example.com/", "TestBot/1.0")
        assert urls == ["https://example.com/sitemap_index.xml"]


async def test_discover_sitemap_urls_falls_back_to_conventional_path():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        urls = await discover_sitemap_urls(client, "https://example.com/", "TestBot/1.0")
        assert urls == ["https://example.com/sitemap.xml"]


async def test_fetch_sitemap_page_urls_recurses_through_index():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        page_urls = await fetch_sitemap_page_urls(
            client, "https://example.com/sitemap_index.xml", "TestBot/1.0"
        )
        assert page_urls == ["https://example.com/a", "https://example.com/b"]
