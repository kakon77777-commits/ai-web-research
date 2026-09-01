from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from ai_web_research.core.types import ArtifactKind
from ai_web_research.execution.models import ProviderObservation
from .models import DiscoveryBatch, DiscoveryCandidate


def _normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or '/'
    if path != '/' and path.endswith('/'):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, parts.query, ''))


def normalize_discovery_observation(observation: ProviderObservation) -> DiscoveryBatch:
    by_url: dict[str, DiscoveryCandidate] = {}
    order: list[str] = []
    for artifact in observation.artifacts:
        if artifact.kind is not ArtifactKind.CANDIDATE:
            continue
        raw_url = artifact.metadata.get('url')
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        url = _normalize_url(raw_url)
        rank_raw = artifact.metadata.get('provider_rank', len(order) + 1)
        rank = rank_raw if isinstance(rank_raw, int) and not isinstance(rank_raw, bool) else len(order) + 1
        existing = by_url.get(url)
        if existing is not None:
            by_url[url] = replace(existing, artifact_ids=existing.artifact_ids + (artifact.id,))
            continue
        candidate_id = 'discovery:' + sha256(f'{observation.provider_id}|{url}'.encode('utf-8')).hexdigest()[:24]
        metadata = dict(artifact.metadata)
        by_url[url] = DiscoveryCandidate(
            candidate_id=candidate_id,
            url=url,
            title=str(metadata.get('title')) if metadata.get('title') is not None else None,
            snippet=str(metadata.get('description')) if metadata.get('description') is not None else None,
            provider_id=observation.provider_id,
            surface_id=observation.surface_id,
            provider_rank=rank,
            artifact_ids=(artifact.id,),
            metadata=metadata,
        )
        order.append(url)
    candidates = tuple(sorted((by_url[url] for url in order), key=lambda c: (c.provider_rank, c.candidate_id)))
    query = observation.metadata.get('query')
    return DiscoveryBatch(
        observation_id=observation.observation_id,
        query=str(query) if query is not None else '',
        candidates=candidates,
        provider_id=observation.provider_id,
        occurred_at=observation.occurred_at,
    )
