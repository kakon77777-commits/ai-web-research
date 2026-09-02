from __future__ import annotations

from hashlib import sha256
from ai_web_research.core.types import ArtifactKind, ArtifactRef


def url_candidate_artifacts(
    rows: list[dict[str, object]],
    *,
    id_prefix: str,
    source_type: str,
) -> tuple[ArtifactRef, ...]:
    """Create deterministic discovery-only candidates, preserving first URL occurrence."""
    seen: set[str] = set()
    artifacts: list[ArtifactRef] = []
    for row in rows:
        raw_url = row.get("url")
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        url = raw_url.strip()
        if url in seen:
            continue
        seen.add(url)
        title = row.get("title")
        snippet = row.get("snippet")
        metadata = {
            "url": url,
            "title": str(title) if title is not None else None,
            "snippet": str(snippet) if snippet is not None else None,
            "provider_rank": len(artifacts) + 1,
            "source_type": source_type,
            "external_source": True,
            "evidence_role": "discovery_only",
            "model_native": True,
        }
        artifacts.append(
            ArtifactRef(
                ArtifactKind.CANDIDATE,
                f"{id_prefix}:url:{sha256(url.encode('utf-8')).hexdigest()[:24]}",
                metadata=metadata,
            )
        )
    return tuple(artifacts)
