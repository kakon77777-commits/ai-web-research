from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.evidence.models import AcquiredAsset

TextReader = Callable[[str], str]
DEFAULT_MAX_CHARS = 1_000_000


class FetchedPageError(ValueError):
    pass


@dataclass(frozen=True)
class FetchedPage:
    source_id: str
    url: str
    canonical_url: str | None
    html: str
    observed_at: str
    published_at: str | None
    content_hash: str | None
    title: str | None
    author: str | None
    content_ref: str
    truncated: bool


def _normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        raise FetchedPageError(f"absolute URL required: {value!r}")
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _read_bounded(content_ref: str, reader: TextReader, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        raise FetchedPageError("max_chars must be positive")
    value = reader(content_ref)
    if not isinstance(value, str):
        raise FetchedPageError("fetched page reader must return text")
    return value[:max_chars], len(value) > max_chars


def fetched_page_from_document(
    document: ArtifactRef,
    reader: TextReader,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> FetchedPage:
    if document.kind != ArtifactKind.DOCUMENT:
        raise FetchedPageError("document artifact required")
    metadata = document.metadata
    raw_url = metadata.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise FetchedPageError("DOCUMENT artifact is missing URL")
    normalized_url = _normalize_url(raw_url)
    content_ref = metadata.get("raw_path") or metadata.get("markdown_path")
    if not isinstance(content_ref, str) or not content_ref.strip():
        raise FetchedPageError("DOCUMENT artifact has no local content reference")
    html, truncated = _read_bounded(content_ref, reader, max_chars)
    observed_at = metadata.get("fetched_at")
    if not isinstance(observed_at, str) or not observed_at:
        raise FetchedPageError("DOCUMENT artifact is missing fetched_at")
    explicit_source_id = metadata.get("source_id")
    source_id = (
        explicit_source_id
        if isinstance(explicit_source_id, str) and explicit_source_id.strip()
        else f"source:{normalized_url}"
    )
    canonical = metadata.get("canonical_url")
    return FetchedPage(
        source_id=source_id,
        url=raw_url,
        canonical_url=canonical if isinstance(canonical, str) and canonical else None,
        html=html,
        observed_at=observed_at,
        published_at=metadata.get("published_at") if isinstance(metadata.get("published_at"), str) else None,
        content_hash=metadata.get("content_hash") if isinstance(metadata.get("content_hash"), str) else None,
        title=metadata.get("title") if isinstance(metadata.get("title"), str) else None,
        author=metadata.get("author") if isinstance(metadata.get("author"), str) else None,
        content_ref=content_ref,
        truncated=truncated,
    )


def fetched_page_from_asset(
    asset: AcquiredAsset,
    reader: TextReader,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> FetchedPage:
    document = asset.artifact_ref
    if document.kind != ArtifactKind.DOCUMENT:
        raise FetchedPageError("AcquiredAsset must reference a DOCUMENT artifact")
    metadata = dict(document.metadata)
    if asset.raw_ref:
        metadata["raw_path"] = asset.raw_ref
    metadata["fetched_at"] = asset.retrieved_at
    if asset.content_hash is not None:
        metadata["content_hash"] = asset.content_hash
    bridged = ArtifactRef(document.kind, document.id, document.version, metadata)
    return fetched_page_from_document(bridged, reader, max_chars=max_chars)
