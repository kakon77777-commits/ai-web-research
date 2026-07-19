"""Deterministic (no-LLM) extraction of title/author/date/links from raw HTML.

Stage 1 scope deliberately excludes LLM extraction (doc section: AI 負責理解與例外,
確定性程式負責約束) — this module only reads explicit meta tags, OG tags and JSON-LD.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .normalize import resolve


@dataclass
class PageMeta:
    title: str | None = None
    author: str | None = None
    published_at: str | None = None
    canonical_url: str | None = None
    language: str | None = None


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            objects.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            objects.append(data)
    return objects


def extract_metadata(html: str, base_url: str) -> PageMeta:
    soup = BeautifulSoup(html, "lxml")
    meta = PageMeta()
    json_ld = _json_ld_objects(soup)

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        meta.title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        meta.title = soup.title.string.strip()
    else:
        h1 = soup.find("h1")
        if h1:
            meta.title = h1.get_text(strip=True)

    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta and author_meta.get("content"):
        meta.author = author_meta["content"].strip()
    else:
        for obj in json_ld:
            author = obj.get("author")
            if isinstance(author, dict) and author.get("name"):
                meta.author = author["name"]
                break
            if isinstance(author, str):
                meta.author = author
                break

    published_meta = soup.find("meta", property="article:published_time")
    if published_meta and published_meta.get("content"):
        meta.published_at = published_meta["content"].strip()
    else:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            meta.published_at = time_tag["datetime"].strip()
        else:
            for obj in json_ld:
                date_published = obj.get("datePublished")
                if date_published:
                    meta.published_at = date_published
                    break

    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        meta.canonical_url = resolve(base_url, canonical["href"])

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        meta.language = html_tag["lang"].strip()

    return meta


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        urls.append(resolve(base_url, href))
    return urls
