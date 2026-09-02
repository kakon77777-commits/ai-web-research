from __future__ import annotations

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.evidence.models import AcquiredAsset
from ai_web_research.source_graph.fetched_page import (
    FetchedPageError,
    fetched_page_from_asset,
    fetched_page_from_document,
)


def _document(**overrides):
    meta = {
        "url": "https://Media.Example/story/",
        "canonical_url": "https://media.example/story",
        "raw_path": "/snapshots/story.html",
        "markdown_path": "/snapshots/story.md",
        "content_hash": "abc123",
        "fetched_at": "2026-09-01T12:00:00Z",
        "published_at": "2026-09-01T11:00:00Z",
        "title": "Story",
        "author": "Reporter",
    }
    meta.update(overrides)
    return ArtifactRef(ArtifactKind.DOCUMENT, "doc:1", metadata=meta)


def test_document_bridge_reads_local_raw_ref_and_preserves_metadata():
    calls = []
    page = fetched_page_from_document(
        _document(), lambda ref: calls.append(ref) or "<html>hello</html>"
    )
    assert calls == ["/snapshots/story.html"]
    assert page.source_id == "source:https://media.example/story"
    assert page.url == "https://Media.Example/story/"
    assert page.canonical_url == "https://media.example/story"
    assert page.content_hash == "abc123"
    assert page.observed_at == "2026-09-01T12:00:00Z"
    assert page.published_at == "2026-09-01T11:00:00Z"
    assert page.title == "Story"
    assert page.author == "Reporter"
    assert page.content_ref == "/snapshots/story.html"
    assert page.truncated is False


def test_asset_bridge_prefers_asset_raw_ref():
    calls = []
    asset = AcquiredAsset(
        asset_id="asset:1", observation_id="obs:1", provider_id="provider.crawler",
        surface_id="surface.crawler.browser", artifact_ref=_document(raw_path="/artifact.html"),
        raw_ref="/asset.html", media_type="text/html", retrieved_at="2026-09-01T12:01:00Z",
        content_hash="asset-hash", usage_envelope_id="usage:1", acquisition_event_id="acq:1",
    )
    page = fetched_page_from_asset(asset, lambda ref: calls.append(ref) or "<p>x</p>")
    assert calls == ["/asset.html"]
    assert page.content_ref == "/asset.html"
    assert page.observed_at == "2026-09-01T12:01:00Z"
    assert page.content_hash == "asset-hash"


def test_asset_bridge_falls_back_to_document_content_ref():
    calls = []
    asset = AcquiredAsset(
        asset_id="asset:1", observation_id="obs:1", provider_id="p", surface_id="s",
        artifact_ref=_document(raw_path=None, markdown_path="/page.md"), raw_ref=None,
        media_type="text/markdown", retrieved_at="2026-09-01T12:01:00Z", content_hash=None,
        usage_envelope_id="usage:1", acquisition_event_id="acq:1",
    )
    page = fetched_page_from_asset(asset, lambda ref: calls.append(ref) or "content")
    assert calls == ["/page.md"]
    assert page.content_ref == "/page.md"


def test_bridge_fails_closed_without_url_or_content_ref():
    with pytest.raises(FetchedPageError):
        fetched_page_from_document(_document(url=None), lambda _: "x")
    with pytest.raises(FetchedPageError):
        fetched_page_from_document(_document(raw_path=None, markdown_path=None), lambda _: "x")


def test_bridge_truncates_deterministically_at_max_chars():
    page = fetched_page_from_document(_document(), lambda _: "abcdef", max_chars=4)
    assert page.html == "abcd"
    assert page.truncated is True
