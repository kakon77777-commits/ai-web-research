from __future__ import annotations

from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.page_signals import PageSignalExtraction, PageSourceSignal, PageSourceSignalKind
from ai_web_research.source_graph.signal_compile import compile_page_source_signals
from ai_web_research.source_graph.models import SourceRelationType, RelationInferenceType


def _page(url="https://media.example/story"):
    return FetchedPage(source_id=f"source:{url}", url=url, canonical_url=None, html="", observed_at="2026-09-01T12:00:00Z", published_at=None, content_hash=None, title=None, author=None, content_ref="fixture", truncated=False)


def _sig(kind, value, n=1):
    return PageSourceSignal(signal_id=f"sig:{kind.value}:{n}", source_id="source:https://media.example/story", kind=kind, value=value, locator=f"loc:{n}", confidence=1.0, explicit=True)


def _extraction(*signals):
    return PageSignalExtraction(source_id="source:https://media.example/story", signals=signals, warnings=(), truncated=False, parser_version="test")


def test_self_canonical_creates_no_relation_but_different_canonical_mirrors():
    self_result = compile_page_source_signals(_page(), _extraction(_sig(PageSourceSignalKind.CANONICAL_URL, "https://media.example/story")))
    assert self_result.relations == ()
    result = compile_page_source_signals(_page(), _extraction(_sig(PageSourceSignalKind.CANONICAL_URL, "https://origin.example/story")))
    assert len(result.relations) == 1
    rel = result.relations[0]
    assert rel.relation_type == SourceRelationType.MIRRORS
    assert rel.to_source_id == "source:https://origin.example/story"
    assert rel.inference_type == RelationInferenceType.EXPLICIT
    assert rel.confidence == 1.0


def test_strong_structural_signals_compile_to_typed_relations():
    result = compile_page_source_signals(_page(), _extraction(
        _sig(PageSourceSignalKind.SYNDICATION_SOURCE, "https://wire.example/a", 1),
        _sig(PageSourceSignalKind.ORIGINAL_SOURCE, "https://official.example/a", 2),
        _sig(PageSourceSignalKind.BASED_ON, "https://official.example/b", 3),
        _sig(PageSourceSignalKind.CITATION_URL, "https://paper.example/p", 4),
    ))
    assert [r.relation_type for r in result.relations] == [SourceRelationType.SYNDICATED_FROM, SourceRelationType.DERIVED_FROM, SourceRelationType.DERIVED_FROM, SourceRelationType.CITES]
    assert [r.to_source_id for r in result.relations] == ["source:https://wire.example/a", "source:https://official.example/a", "source:https://official.example/b", "source:https://paper.example/p"]


def test_text_attribution_quote_and_owner_are_trace_or_metadata_only():
    result = compile_page_source_signals(_page(), _extraction(
        _sig(PageSourceSignalKind.ATTRIBUTED_URL, "https://source.example/x", 1),
        _sig(PageSourceSignalKind.ATTRIBUTION_ENTITY, "Source Org", 2),
        _sig(PageSourceSignalKind.QUOTED_PHRASE, "A distinctive quoted source phrase.", 3),
        _sig(PageSourceSignalKind.OWNER_HINT, "Media Example", 4),
    ), claim_keywords=("Model X", "release"))
    assert result.relations == ()
    assert result.trace_signals.attributed_source_urls == ("https://source.example/x",)
    assert result.trace_signals.attribution_entities == ("Source Org",)
    assert result.trace_signals.quoted_phrases == ("A distinctive quoted source phrase.",)
    assert result.trace_signals.claim_keywords == ("Model X", "release")
    assert result.owner_hints == ("Media Example",)


def test_structural_urls_are_available_to_trace_planner_while_types_remain_explicit():
    result = compile_page_source_signals(_page(), _extraction(
        _sig(PageSourceSignalKind.SYNDICATION_SOURCE, "https://wire.example/a", 1),
        _sig(PageSourceSignalKind.CITATION_URL, "https://paper.example/p", 2),
    ))
    assert result.trace_signals.attributed_source_urls == ("https://wire.example/a", "https://paper.example/p")
    assert [r.relation_type for r in result.relations] == [SourceRelationType.SYNDICATED_FROM, SourceRelationType.CITES]


def test_duplicate_signal_values_fold_deterministically():
    result = compile_page_source_signals(_page(), _extraction(
        _sig(PageSourceSignalKind.ORIGINAL_SOURCE, "https://official.example/a/", 1),
        _sig(PageSourceSignalKind.ORIGINAL_SOURCE, "https://official.example/a", 2),
        _sig(PageSourceSignalKind.OWNER_HINT, "Media Example", 3),
        _sig(PageSourceSignalKind.OWNER_HINT, "Media Example", 4),
    ))
    assert len(result.relations) == 1
    assert result.owner_hints == ("Media Example",)
