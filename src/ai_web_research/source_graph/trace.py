from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from ai_web_research.discovery.models import DiscoveryCandidate

from .models import RelationInferenceType, SourceNode, SourceRelation, SourceRelationType


class TraceActionKind(StrEnum):
    DIRECT_PREDECESSOR = "direct_predecessor"
    EXACT_QUOTE_SEARCH = "exact_quote_search"
    ENTITY_SEARCH = "entity_search"


@dataclass(frozen=True)
class SourceTraceSignals:
    attributed_source_urls: tuple[str, ...]
    attribution_entities: tuple[str, ...]
    quoted_phrases: tuple[str, ...]
    claim_keywords: tuple[str, ...]


@dataclass(frozen=True)
class TraceAction:
    action_id: str
    kind: TraceActionKind
    query: str | None
    url: str | None
    signal: str


@dataclass(frozen=True)
class ReverseTracePlan:
    source_id: str
    actions: tuple[TraceAction, ...]
    unresolved: bool
    reason: str | None


def _normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _action_id(source_id: str, kind: TraceActionKind, value: str) -> str:
    digest = sha256(f"{source_id}|{kind.value}|{value}".encode("utf-8")).hexdigest()[:20]
    return f"trace-action:{digest}"


def plan_reverse_trace(source_id: str, signals: SourceTraceSignals) -> ReverseTracePlan:
    actions: list[TraceAction] = []

    for raw_url in signals.attributed_source_urls:
        if not raw_url.strip():
            continue
        url = _normalize_url(raw_url)
        actions.append(
            TraceAction(
                action_id=_action_id(source_id, TraceActionKind.DIRECT_PREDECESSOR, url),
                kind=TraceActionKind.DIRECT_PREDECESSOR,
                query=None,
                url=url,
                signal="explicit_attributed_url",
            )
        )

    for phrase in signals.quoted_phrases:
        phrase = phrase.strip()
        if not phrase:
            continue
        query = f'"{phrase}"'
        actions.append(
            TraceAction(
                action_id=_action_id(source_id, TraceActionKind.EXACT_QUOTE_SEARCH, query),
                kind=TraceActionKind.EXACT_QUOTE_SEARCH,
                query=query,
                url=None,
                signal="quoted_phrase",
            )
        )

    keywords = " ".join(keyword.strip() for keyword in signals.claim_keywords if keyword.strip())
    for entity in signals.attribution_entities:
        entity = entity.strip()
        if not entity:
            continue
        query = f'"{entity}"{(" " + keywords) if keywords else ""}'
        actions.append(
            TraceAction(
                action_id=_action_id(source_id, TraceActionKind.ENTITY_SEARCH, query),
                kind=TraceActionKind.ENTITY_SEARCH,
                query=query,
                url=None,
                signal="attribution_entity",
            )
        )

    if not actions:
        return ReverseTracePlan(source_id=source_id, actions=(), unresolved=True, reason="no_trace_signals")
    return ReverseTracePlan(source_id=source_id, actions=tuple(actions), unresolved=False, reason=None)


def materialize_explicit_trace_edges(
    source: SourceNode,
    candidates: tuple[DiscoveryCandidate, ...],
    signals: SourceTraceSignals,
) -> tuple[SourceRelation, ...]:
    attributed = {
        _normalize_url(url)
        for url in signals.attributed_source_urls
        if isinstance(url, str) and url.strip()
    }
    if not attributed:
        return ()

    edges: list[SourceRelation] = []
    seen_targets: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_url(candidate.url)
        if normalized not in attributed or normalized in seen_targets:
            continue
        seen_targets.add(normalized)
        target_id = f"source:{normalized}"
        relation_id = "source-relation:" + sha256(
            f"{source.source_id}|derived_from|{target_id}|explicit_attributed_url".encode("utf-8")
        ).hexdigest()[:20]
        edges.append(
            SourceRelation(
                relation_id=relation_id,
                from_source_id=source.source_id,
                to_source_id=target_id,
                relation_type=SourceRelationType.DERIVED_FROM,
                confidence=1.0,
                inference_type=RelationInferenceType.EXPLICIT,
                signals=("explicit_attributed_url",),
            )
        )
    return tuple(edges)
