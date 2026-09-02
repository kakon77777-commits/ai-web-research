from __future__ import annotations

from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.html_extract import extract_page_source_signals
from ai_web_research.source_graph.page_signals import PageSourceSignalKind


def _page(html: str, *, url: str = "https://media.example/story") -> FetchedPage:
    return FetchedPage(source_id=f"source:{url}", url=url, canonical_url=None, html=html, observed_at="2026-09-01T12:00:00Z", published_at=None, content_hash=None, title=None, author=None, content_ref="fixture.html", truncated=False)


def _values(result, kind):
    return [s.value for s in result.signals if s.kind == kind]


def test_extracts_structural_html_signals_and_resolves_relative_urls():
    html = '''<html><head><link rel="canonical" href="/story"><link rel="syndication-source" href="https://wire.example/original"><link rel="original-source" href="https://official.example/post/"><meta property="og:site_name" content="Media Example"></head><body><blockquote cite="https://research.example/paper">A distinctive quoted phrase about Model X release.</blockquote><q cite="/quoted-source">Another sufficiently long quoted phrase.</q><a href="https://irrelevant.example/">Read more</a></body></html>'''
    result = extract_page_source_signals(_page(html))
    assert _values(result, PageSourceSignalKind.CANONICAL_URL) == ["https://media.example/story"]
    assert _values(result, PageSourceSignalKind.SYNDICATION_SOURCE) == ["https://wire.example/original"]
    assert _values(result, PageSourceSignalKind.ORIGINAL_SOURCE) == ["https://official.example/post"]
    assert _values(result, PageSourceSignalKind.CITATION_URL) == ["https://research.example/paper", "https://media.example/quoted-source"]
    assert _values(result, PageSourceSignalKind.QUOTED_PHRASE) == ["A distinctive quoted phrase about Model X release.", "Another sufficiently long quoted phrase."]
    assert _values(result, PageSourceSignalKind.OWNER_HINT) == ["Media Example"]
    assert all("irrelevant.example" not in s.value for s in result.signals)


def test_extracts_json_ld_based_on_citation_syndication_and_publisher():
    html = '''<script type="application/ld+json">{"@type":"NewsArticle","publisher":{"@type":"Organization","name":"Example News"},"citation":"https://paper.example/one","isBasedOn":{"@id":"https://official.example/source"},"isBasedOnUrl":"https://official.example/source-2","syndicationSource":{"url":"https://wire.example/item"}}</script>'''
    result = extract_page_source_signals(_page(html))
    assert _values(result, PageSourceSignalKind.OWNER_HINT) == ["Example News"]
    assert _values(result, PageSourceSignalKind.CITATION_URL) == ["https://paper.example/one"]
    assert _values(result, PageSourceSignalKind.BASED_ON) == ["https://official.example/source", "https://official.example/source-2"]
    assert _values(result, PageSourceSignalKind.SYNDICATION_SOURCE) == ["https://wire.example/item"]


def test_malformed_json_ld_fails_soft_with_warning():
    result = extract_page_source_signals(_page('<script type="application/ld+json">{"broken":</script>'))
    assert result.signals == ()
    assert "malformed_json_ld" in result.warnings


def test_quote_bounds_drop_too_short_and_clip_long_text():
    long_text = "word " * 80
    result = extract_page_source_signals(_page(f"<q>short</q><blockquote>{long_text}</blockquote>"))
    quotes = _values(result, PageSourceSignalKind.QUOTED_PHRASE)
    assert len(quotes) == 1
    assert 12 <= len(quotes[0]) <= 240
    assert quotes[0].startswith("word word word")


def test_signal_cap_is_deterministic_and_reports_warning():
    links = "".join(f'<link rel="original-source" href="https://source.example/{i}">' for i in range(130))
    result = extract_page_source_signals(_page(f"<head>{links}</head>"))
    assert len(result.signals) == 128
    assert result.signals[0].value == "https://source.example/0"
    assert result.signals[-1].value == "https://source.example/127"
    assert "signal_limit_reached" in result.warnings


def test_linked_attribution_markers_emit_trace_only_signals():
    html = '''<p>According to <a href="https://official.example/post">Official Lab</a>, the model shipped.</p><p>via <a href="/wire">Wire Source</a></p><p>source: <a href="https://source.example/item">Source Desk</a></p>'''
    result = extract_page_source_signals(_page(html))
    assert _values(result, PageSourceSignalKind.ATTRIBUTED_URL) == ["https://official.example/post", "https://media.example/wire", "https://source.example/item"]
    assert _values(result, PageSourceSignalKind.ATTRIBUTION_ENTITY) == ["Official Lab", "Wire Source", "Source Desk"]


def test_generic_or_distant_links_do_not_become_attribution_signals():
    padding = "x" * 90
    html = f'''<p><a href="https://generic.example/">Read more</a></p><p>According to {padding}<a href="https://too-far.example/">Far Source</a></p><nav>via <a href="https://nav.example/">Navigation</a></nav><p>Related: <a href="https://related.example/">Another article</a></p>'''
    result = extract_page_source_signals(_page(html))
    assert _values(result, PageSourceSignalKind.ATTRIBUTED_URL) == []
    assert _values(result, PageSourceSignalKind.ATTRIBUTION_ENTITY) == []
