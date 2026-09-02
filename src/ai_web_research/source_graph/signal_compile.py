from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from urllib.parse import urlsplit, urlunsplit

from .fetched_page import FetchedPage
from .models import RelationInferenceType, SourceRelation, SourceRelationType
from .page_signals import PageSignalExtraction, PageSourceSignalKind
from .trace import SourceTraceSignals

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class CompiledPageSourceSignals:
    source_id: str
    trace_signals: SourceTraceSignals
    relations: tuple[SourceRelation, ...]
    owner_hints: tuple[str, ...]
    signal_ids: tuple[str, ...]


def _space(value: str) -> str:
    return _WS.sub(" ", value).strip()


def _normalize_url(value: str) -> str | None:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _relation(page: FetchedPage, relation_type: SourceRelationType, target_url: str, signal_id: str, locator: str) -> SourceRelation | None:
    normalized = _normalize_url(target_url)
    if normalized is None:
        return None
    target_id = f"source:{normalized}"
    if target_id == page.source_id:
        return None
    relation_id = "source-relation:" + sha256(
        f"{page.source_id}|{relation_type.value}|{target_id}|{signal_id}".encode("utf-8")
    ).hexdigest()[:20]
    return SourceRelation(
        relation_id=relation_id,
        from_source_id=page.source_id,
        to_source_id=target_id,
        relation_type=relation_type,
        confidence=1.0,
        inference_type=RelationInferenceType.EXPLICIT,
        signals=(signal_id, locator),
    )


def compile_page_source_signals(page: FetchedPage, extraction: PageSignalExtraction, *, claim_keywords: tuple[str, ...] = ()) -> CompiledPageSourceSignals:
    if extraction.source_id != page.source_id:
        raise ValueError("page/extraction source mismatch")
    seen: set[tuple[PageSourceSignalKind, str]] = set()
    trace_urls: list[str] = []
    entities: list[str] = []
    quotes: list[str] = []
    owners: list[str] = []
    relations: list[SourceRelation] = []
    signal_ids: list[str] = []
    page_url = _normalize_url(page.url)
    relation_types = {
        PageSourceSignalKind.SYNDICATION_SOURCE: SourceRelationType.SYNDICATED_FROM,
        PageSourceSignalKind.ORIGINAL_SOURCE: SourceRelationType.DERIVED_FROM,
        PageSourceSignalKind.BASED_ON: SourceRelationType.DERIVED_FROM,
        PageSourceSignalKind.CITATION_URL: SourceRelationType.CITES,
    }
    for signal in extraction.signals:
        if signal.kind in {PageSourceSignalKind.CANONICAL_URL, PageSourceSignalKind.SYNDICATION_SOURCE, PageSourceSignalKind.ORIGINAL_SOURCE, PageSourceSignalKind.BASED_ON, PageSourceSignalKind.CITATION_URL, PageSourceSignalKind.ATTRIBUTED_URL}:
            value = _normalize_url(signal.value)
            if value is None:
                continue
        else:
            value = _space(signal.value)
            if not value:
                continue
        key = (signal.kind, value)
        if key in seen:
            continue
        seen.add(key)
        signal_ids.append(signal.signal_id)
        if signal.kind == PageSourceSignalKind.CANONICAL_URL:
            if value != page_url:
                rel = _relation(page, SourceRelationType.MIRRORS, value, signal.signal_id, signal.locator)
                if rel is not None:
                    relations.append(rel)
            continue
        relation_type = relation_types.get(signal.kind)
        if relation_type is not None:
            rel = _relation(page, relation_type, value, signal.signal_id, signal.locator)
            if rel is not None:
                relations.append(rel)
            if value not in trace_urls:
                trace_urls.append(value)
            continue
        if signal.kind == PageSourceSignalKind.ATTRIBUTED_URL:
            if value not in trace_urls:
                trace_urls.append(value)
        elif signal.kind == PageSourceSignalKind.ATTRIBUTION_ENTITY:
            if value not in entities:
                entities.append(value)
        elif signal.kind == PageSourceSignalKind.QUOTED_PHRASE:
            if value not in quotes:
                quotes.append(value)
        elif signal.kind == PageSourceSignalKind.OWNER_HINT:
            if value not in owners:
                owners.append(value)
    keywords = tuple(_space(value) for value in claim_keywords if _space(value))
    return CompiledPageSourceSignals(
        source_id=page.source_id,
        trace_signals=SourceTraceSignals(
            attributed_source_urls=tuple(trace_urls),
            attribution_entities=tuple(entities),
            quoted_phrases=tuple(quotes),
            claim_keywords=keywords,
        ),
        relations=tuple(relations),
        owner_hints=tuple(owners),
        signal_ids=tuple(signal_ids),
    )
