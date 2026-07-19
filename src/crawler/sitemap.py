"""Sitemap discovery and parsing (urlset + sitemapindex, recursive)."""

from __future__ import annotations

from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_DEFAULT_MAX_SITEMAP_DOCS = 10


async def discover_sitemap_urls(client: httpx.AsyncClient, base_url: str, user_agent: str, timeout: float = 15.0) -> list[str]:
    """Find sitemap.xml locations via robots.txt Sitemap: directives, falling
    back to the conventional /sitemap.xml path."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates: list[str] = []

    robots_url = f"{root}/robots.txt"
    try:
        resp = await client.get(robots_url, timeout=timeout, headers={"User-Agent": user_agent})
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    candidates.append(line.split(":", 1)[1].strip())
    except httpx.HTTPError:
        pass

    if not candidates:
        candidates.append(f"{root}/sitemap.xml")

    return candidates


async def fetch_sitemap_page_urls(
    client: httpx.AsyncClient,
    sitemap_url: str,
    user_agent: str,
    timeout: float = 15.0,
    max_sitemap_docs: int = _DEFAULT_MAX_SITEMAP_DOCS,
) -> list[str]:
    """Fetch a sitemap (or sitemap index) and return all page URLs found,
    recursing into child sitemaps up to max_sitemap_docs total documents."""
    page_urls: list[str] = []
    queue = [sitemap_url]
    seen_docs = 0

    while queue and seen_docs < max_sitemap_docs:
        current = queue.pop(0)
        seen_docs += 1
        try:
            resp = await client.get(current, timeout=timeout, headers={"User-Agent": user_agent})
            if resp.status_code != 200:
                continue
            root = ElementTree.fromstring(resp.content)
        except (httpx.HTTPError, ElementTree.ParseError):
            continue

        tag = root.tag
        if tag.endswith("sitemapindex"):
            for loc_el in root.iter(f"{_SITEMAP_NS}loc"):
                if loc_el.text:
                    queue.append(loc_el.text.strip())
        elif tag.endswith("urlset"):
            for loc_el in root.iter(f"{_SITEMAP_NS}loc"):
                if loc_el.text:
                    page_urls.append(loc_el.text.strip())

    return page_urls
