from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from .fetched_page import FetchedPage
from .page_signals import PageSignalExtraction, PageSourceSignal, PageSourceSignalKind

PARSER_VERSION = "page-source-signals-html-v0.1"
MAX_SIGNALS = 128
MAX_JSON_NODES = 2_048
MIN_QUOTE_CHARS = 12
MAX_QUOTE_CHARS = 240
MAX_ATTRIBUTION_CONTEXT = 80
BLOCK_TAGS = {"p", "li", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}
EXCLUDED_ATTRIBUTION_TAGS = {"nav", "header", "footer", "aside"}

_WS = re.compile(r"\s+")


def _space(value: str) -> str:
    return _WS.sub(" ", value).strip()


def _normalize_url(base: str, value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    absolute = urljoin(base, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _url_values(base: str, value: Any) -> list[str]:
    raw_values: list[str] = []
    if isinstance(value, str):
        raw_values.append(value)
    elif isinstance(value, list):
        for item in value:
            raw_values.extend(_url_values(base, item))
        return list(dict.fromkeys(raw_values))
    elif isinstance(value, dict):
        for key in ("url", "@id"):
            item = value.get(key)
            if isinstance(item, str):
                raw_values.append(item)
    result: list[str] = []
    for raw in raw_values:
        normalized = _normalize_url(base, raw)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


class _SignalParser(HTMLParser):
    def __init__(self, page: FetchedPage) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page
        self.signals: list[PageSourceSignal] = []
        self.warnings: list[str] = []
        self.counts: dict[str, int] = {}
        self.quote_stack: list[dict[str, Any]] = []
        self.jsonld_stack: list[dict[str, Any]] = []
        self.anchor_stack: list[dict[str, Any]] = []
        self.block_context = ""
        self.excluded_attribution_depth = 0
        self._signal_limit_warned = False

    def _next(self, name: str) -> int:
        value = self.counts.get(name, 0) + 1
        self.counts[name] = value
        return value

    def _warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    def _emit(self, kind: PageSourceSignalKind, value: str, locator: str, *, confidence: float = 1.0, explicit: bool = True) -> None:
        value = _space(value)
        if not value:
            return
        if len(self.signals) >= MAX_SIGNALS:
            if not self._signal_limit_warned:
                self._warn("signal_limit_reached")
                self._signal_limit_warned = True
            return
        signal_id = "page-signal:" + sha256(f"{self.page.source_id}|{kind.value}|{value}|{locator}".encode("utf-8")).hexdigest()[:20]
        self.signals.append(PageSourceSignal(signal_id=signal_id, source_id=self.page.source_id, kind=kind, value=value, locator=locator, confidence=confidence, explicit=explicit))

    def _emit_url(self, kind: PageSourceSignalKind, raw: str, locator: str) -> None:
        normalized = _normalize_url(self.page.url, raw)
        if normalized:
            self._emit(kind, normalized, locator)

    def _append_context(self, data: str) -> None:
        text = _space(data)
        if not text:
            return
        combined = _space(f"{self.block_context} {text}")
        self.block_context = combined[-MAX_ATTRIBUTION_CONTEXT:]

    def _context_has_attribution_marker(self) -> bool:
        return bool(re.search(r"(?:according to|via|source\s*:)\s*$", self.block_context, re.IGNORECASE))

    def handle_starttag(self, tag: str, attrs) -> None:
        amap = {str(k).lower(): v for k, v in attrs if k}
        tag = tag.lower()
        if tag in BLOCK_TAGS:
            self.block_context = ""
        if tag in EXCLUDED_ATTRIBUTION_TAGS:
            self.excluded_attribution_depth += 1
        if tag == "link":
            index = self._next("link")
            rel = {part.lower() for part in str(amap.get("rel") or "").split()}
            href = amap.get("href")
            if isinstance(href, str):
                if "canonical" in rel:
                    self._emit_url(PageSourceSignalKind.CANONICAL_URL, href, f"link[{index}]:rel=canonical")
                if "syndication-source" in rel:
                    self._emit_url(PageSourceSignalKind.SYNDICATION_SOURCE, href, f"link[{index}]:rel=syndication-source")
                if "original-source" in rel:
                    self._emit_url(PageSourceSignalKind.ORIGINAL_SOURCE, href, f"link[{index}]:rel=original-source")
        elif tag == "meta":
            index = self._next("meta")
            prop = str(amap.get("property") or amap.get("name") or "").lower()
            content = amap.get("content")
            if prop == "og:site_name" and isinstance(content, str):
                self._emit(PageSourceSignalKind.OWNER_HINT, content, f"meta[{index}]:og:site_name")
        elif tag in {"blockquote", "q"}:
            index = self._next(tag)
            cite = amap.get("cite")
            if isinstance(cite, str):
                self._emit_url(PageSourceSignalKind.CITATION_URL, cite, f"{tag}[{index}]:cite")
            self.quote_stack.append({"tag": tag, "index": index, "parts": []})
        elif tag == "a":
            index = self._next("a")
            href = amap.get("href")
            resolved = _normalize_url(self.page.url, href) if isinstance(href, str) else None
            attributed = resolved is not None and self.excluded_attribution_depth == 0 and self._context_has_attribution_marker()
            self.anchor_stack.append({"index": index, "url": resolved, "attributed": attributed, "parts": []})
        elif tag == "script" and str(amap.get("type") or "").lower() == "application/ld+json":
            index = self._next("jsonld")
            self.jsonld_stack.append({"index": index, "parts": []})

    def handle_data(self, data: str) -> None:
        if self.quote_stack:
            self.quote_stack[-1]["parts"].append(data)
        if self.anchor_stack:
            self.anchor_stack[-1]["parts"].append(data)
        if self.jsonld_stack:
            self.jsonld_stack[-1]["parts"].append(data)
            return
        if self.excluded_attribution_depth == 0:
            self._append_context(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self.anchor_stack:
            ctx = self.anchor_stack.pop()
            if ctx["attributed"] and ctx["url"]:
                self._emit(PageSourceSignalKind.ATTRIBUTED_URL, ctx["url"], f"a[{ctx['index']}]:attribution")
                entity = _space(" ".join(ctx["parts"]))
                if 2 <= len(entity) <= 120:
                    self._emit(PageSourceSignalKind.ATTRIBUTION_ENTITY, entity, f"a[{ctx['index']}]:text")
        if tag in EXCLUDED_ATTRIBUTION_TAGS and self.excluded_attribution_depth > 0:
            self.excluded_attribution_depth -= 1
        if tag in BLOCK_TAGS:
            self.block_context = ""
        if tag in {"blockquote", "q"} and self.quote_stack:
            ctx = self.quote_stack.pop()
            if ctx["tag"] != tag:
                return
            text = _space(" ".join(ctx["parts"]))
            if len(text) >= MIN_QUOTE_CHARS:
                text = text[:MAX_QUOTE_CHARS].rstrip()
                self._emit(PageSourceSignalKind.QUOTED_PHRASE, text, f"{tag}[{ctx['index']}]:text")
        elif tag == "script" and self.jsonld_stack:
            ctx = self.jsonld_stack.pop()
            raw = "".join(ctx["parts"]).strip()
            if not raw:
                return
            try:
                value = json.loads(raw)
            except Exception:
                self._warn("malformed_json_ld")
                return
            self._walk_jsonld(value, f"jsonld[{ctx['index']}]:$")

    def _walk_jsonld(self, root: Any, root_locator: str) -> None:
        stack: list[tuple[Any, str]] = [(root, root_locator)]
        visited = 0
        while stack:
            value, locator = stack.pop()
            visited += 1
            if visited > MAX_JSON_NODES:
                self._warn("json_ld_node_limit_reached")
                return
            if isinstance(value, list):
                for index in range(len(value) - 1, -1, -1):
                    stack.append((value[index], f"{locator}[{index}]"))
                continue
            if not isinstance(value, dict):
                continue
            publisher = value.get("publisher")
            if isinstance(publisher, dict):
                name = publisher.get("name")
                if isinstance(name, str):
                    self._emit(PageSourceSignalKind.OWNER_HINT, name, f"{locator}.publisher.name")
            mappings = (("citation", PageSourceSignalKind.CITATION_URL), ("isBasedOn", PageSourceSignalKind.BASED_ON), ("isBasedOnUrl", PageSourceSignalKind.BASED_ON), ("syndicationSource", PageSourceSignalKind.SYNDICATION_SOURCE))
            for field, kind in mappings:
                if field in value:
                    for resolved in _url_values(self.page.url, value[field]):
                        self._emit(kind, resolved, f"{locator}.{field}")
            items = list(value.items())
            for key, child in reversed(items):
                if key == "publisher" or key in {m[0] for m in mappings}:
                    continue
                if isinstance(child, (dict, list)):
                    stack.append((child, f"{locator}.{key}"))


def extract_page_source_signals(page: FetchedPage) -> PageSignalExtraction:
    parser = _SignalParser(page)
    try:
        parser.feed(page.html)
        parser.close()
    except Exception as exc:
        parser._warn(f"html_parse_error:{type(exc).__name__}")
    return PageSignalExtraction(source_id=page.source_id, signals=tuple(parser.signals), warnings=tuple(parser.warnings), truncated=page.truncated, parser_version=PARSER_VERSION)
