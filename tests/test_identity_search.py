import json
from pathlib import Path

import httpx

from crawler.identity_search import (
    identity_search,
    normalize_query,
    score_document,
    tokenize,
    trigrams,
)
from crawler.llm import LlmConfig
from crawler.store import PageRecord, PageStore, write_parsed


def _config() -> LlmConfig:
    return LlmConfig(provider="anthropic", api_key="test-key", model="claude-haiku-4-5-20251001")


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# -- pure functions -------------------------------------------------------


def test_normalize_query_folds_width_case_and_whitespace():
    assert normalize_query("  Hello   World  ") == "hello world"
    assert normalize_query("ＡＢＣ") == "abc"  # NFKC fullwidth -> halfwidth
    assert normalize_query(None) == ""
    assert normalize_query("") == ""


def test_tokenize_splits_latin_runs_and_cjk_bigrams():
    assert tokenize("hello world") == ["hello", "world"]
    assert tokenize("動態不動點") == ["動態", "態不", "不動", "動點"]
    assert tokenize("a") == ["a"]
    assert tokenize("中") == ["中"]


def test_trigrams_basic():
    assert trigrams("abcde") == ["abc", "bcd", "cde"]
    assert trigrams("ab") == ["ab"]
    assert trigrams("") == []


def test_score_document_exact_title_beats_lexical_only():
    exact = score_document(
        title_norm="crawl4ai local crawler", content_norm="", token_set=set(), trigram_set=set(),
        query_norm="crawl4ai", query_tokens=["crawl4ai"], query_trigrams=trigrams("crawl4ai"),
    )
    assert "exact" in exact.channels
    assert exact.score == 1.0

    lexical = score_document(
        title_norm="something else entirely", content_norm="", token_set={"crawl4ai"}, trigram_set=set(),
        query_norm="crawl4ai", query_tokens=["crawl4ai"], query_trigrams=trigrams("crawl4ai"),
    )
    assert lexical.channels == ["lexical"]
    assert 0 < lexical.score < exact.score


def test_score_document_zero_for_no_overlap():
    r = score_document(
        title_norm="apple", content_norm="banana", token_set={"apple", "banana"}, trigram_set=set(),
        query_norm="zzz", query_tokens=["zzz"], query_trigrams=trigrams("zzz"),
    )
    assert r.score == 0.0
    assert r.channels == []


# -- identity_search() over a real seeded store ---------------------------


def _seed_store(tmp_path: Path) -> PageStore:
    store = PageStore(tmp_path / "crawl.db")
    md_dir = tmp_path / "parsed"

    pages = [
        ("https://example.com/crawl4ai", "example.com", "Crawl4AI overview",
         "Crawl4AI is a local, self-hosted, LLM-friendly web crawler."),
        ("https://example.com/firecrawl", "example.com", "Firecrawl platform",
         "Firecrawl provides a full web context API and agent data platform."),
        ("https://example.com/unrelated", "example.com", "Weather forecast",
         "Tomorrow will be sunny with a light breeze."),
    ]
    for url, domain, title, content in pages:
        doc_id = __import__("crawler.store", fromlist=["document_id_for"]).document_id_for(url)
        md_path = write_parsed(md_dir, domain, doc_id, content)
        store.upsert(
            PageRecord(
                url=url, canonical_url=None, domain=domain, fetched_at="2026-08-16T00:00:00+00:00",
                published_at=None, status_code=200, content_type="text/html",
                raw_path=None, markdown_path=str(md_path), content_hash=doc_id,
                language="en", title=title, author=None, license_hint=None, robots_allowed=True,
            ),
            unchanged=False,
        )
    return store


async def test_identity_search_finds_exact_title_match(tmp_path: Path):
    store = _seed_store(tmp_path)
    result = await identity_search("Crawl4AI", store)

    assert result.objects, "expected at least one hit"
    top = result.objects[0]
    assert top.url == "https://example.com/crawl4ai"
    assert top.has_exact is True
    store.close()


async def test_identity_search_ranks_exact_above_lexical_only(tmp_path: Path):
    store = _seed_store(tmp_path)
    # "web crawler" appears verbatim in crawl4ai's content but only
    # partially overlaps firecrawl's ("web context") — exact should win.
    result = await identity_search("web crawler", store)

    urls = [o.url for o in result.objects]
    assert urls[0] == "https://example.com/crawl4ai"
    store.close()


async def test_identity_search_returns_no_objects_for_unrelated_query(tmp_path: Path):
    # A digit string shares zero trigrams/tokens with any seeded doc's text
    # by construction — a word-based "unrelated" query (e.g. "nonexistent
    # topic") isn't a safe choice here: trigram overlap is a genuinely
    # fuzzy character-level signal, and English prose can share a few
    # 3-character runs by pure coincidence even between unrelated topics,
    # same as the original semantic-core.js algorithm this was ported from.
    store = _seed_store(tmp_path)
    result = await identity_search("9999888877776666", store)
    assert result.objects == []
    store.close()


async def test_identity_search_folds_multi_branch_hits_to_one_object(tmp_path: Path):
    """Two branches that both hit the SAME document must fold into ONE
    SearchObject carrying multiple path entries — not two separate
    objects. This is the actual identity-fold behavior the whole module
    exists for, exercised through the real identity_search() entry point
    with a mocked divergence call, not a hand-rolled reimplementation."""
    store = _seed_store(tmp_path)

    payload = {
        "branches": {
            "semantic": ["self-hosted crawler"], "task": [], "source": [], "language": [], "perspective": [],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await identity_search(
            "Crawl4AI", store, _config(), use_divergence=True, client=client,
        )

    assert result.branches == ["original", "semantic"]
    top = result.objects[0]
    assert top.url == "https://example.com/crawl4ai"
    # both branches independently matched this same document (title-exact
    # for "Crawl4AI", content-exact for "self-hosted crawler") — the fold
    # must carry both as separate paths on ONE object, not split into two.
    branch_types_seen = {p.branch_type for p in top.paths}
    assert branch_types_seen == {"original", "semantic"}
    store.close()
