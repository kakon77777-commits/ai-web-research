from pathlib import Path

from crawler.extract import extract_links, extract_metadata

FIXTURE = (Path(__file__).parent / "fixtures" / "sample.html").read_text(encoding="utf-8")
BASE_URL = "https://example.com/articles/example-page"


def test_prefers_og_title_over_title_tag_and_h1():
    meta = extract_metadata(FIXTURE, BASE_URL)
    assert meta.title == "範例文章標題"


def test_prefers_meta_author_over_json_ld():
    meta = extract_metadata(FIXTURE, BASE_URL)
    assert meta.author == "許筌崴"


def test_prefers_article_published_time_over_json_ld():
    meta = extract_metadata(FIXTURE, BASE_URL)
    assert meta.published_at == "2026-07-14T09:00:00+08:00"


def test_resolves_canonical_url_against_base():
    meta = extract_metadata(FIXTURE, BASE_URL)
    assert meta.canonical_url == "https://example.com/articles/example"


def test_extracts_language():
    meta = extract_metadata(FIXTURE, BASE_URL)
    assert meta.language == "zh-TW"


def test_extract_links_resolves_and_filters_noise():
    links = extract_links(FIXTURE, BASE_URL)
    assert "https://example.com/articles/next" in links
    assert "https://external.example/other" in links
    assert not any(link.startswith("#") for link in links)
    assert not any(link.startswith("mailto:") for link in links)
