from pathlib import Path

from crawler.store import (
    ExtractionRecord,
    PageRecord,
    PageStore,
    document_id_for,
    sha256_hex,
    write_parsed,
    write_raw,
)


def _record(url: str, content_hash: str) -> PageRecord:
    return PageRecord(
        url=url,
        canonical_url=None,
        domain="example.com",
        fetched_at="2026-07-14T00:00:00+00:00",
        published_at=None,
        status_code=200,
        content_type="text/html",
        raw_path=None,
        markdown_path=None,
        content_hash=content_hash,
        language="zh-TW",
        title="Title",
        author="Author",
        license_hint=None,
        robots_allowed=True,
    )


def test_sha256_hex_is_deterministic():
    assert sha256_hex("hello") == sha256_hex(b"hello")
    assert sha256_hex("hello") != sha256_hex("world")


def test_previous_hash_is_none_for_unseen_url(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    assert store.previous_hash("https://example.com/a") is None
    store.close()


def test_upsert_and_previous_hash_roundtrip(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    record = _record("https://example.com/a", content_hash="hash-1")
    store.upsert(record, unchanged=False)
    assert store.previous_hash("https://example.com/a") == "hash-1"
    store.close()


def test_upsert_marks_unchanged_since_on_repeat_hash(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    record = _record("https://example.com/a", content_hash="hash-1")
    store.upsert(record, unchanged=False)
    store.upsert(record, unchanged=True)

    rows = store.all_pages()
    assert len(rows) == 1
    assert rows[0]["unchanged_since"] == "2026-07-14T00:00:00+00:00"
    store.close()


def test_document_id_is_stable_for_same_url():
    assert document_id_for("https://example.com/a") == document_id_for("https://example.com/a")
    assert document_id_for("https://example.com/a") != document_id_for("https://example.com/b")


def test_write_raw_and_parsed_create_files(tmp_path: Path):
    raw_path = write_raw(tmp_path / "raw", "example.com", "doc123", "<html></html>")
    parsed_path = write_parsed(tmp_path / "parsed", "example.com", "doc123", "# Title")

    assert raw_path.read_text(encoding="utf-8") == "<html></html>"
    assert parsed_path.read_text(encoding="utf-8") == "# Title"


def test_pages_by_domain_filters_correctly(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.upsert(_record("https://example.com/a", content_hash="h1"), unchanged=False)
    other = _record("https://other.com/a", content_hash="h2")
    other.domain = "other.com"
    store.upsert(other, unchanged=False)

    rows = store.pages_by_domain("example.com")
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/a"
    store.close()


def _extraction_record(document_id: str, extractor_version: str = "v1") -> ExtractionRecord:
    return ExtractionRecord(
        document_id=document_id,
        extractor_version=extractor_version,
        url="https://example.com/a",
        provider="vertex",
        model="gemini-2.5-flash-lite",
        extracted_json='{"summary": {"value": "ok"}}',
        validation_errors=None,
        created_at="2026-07-20T00:00:00+00:00",
    )


def test_save_and_get_extraction_roundtrip(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    record = _extraction_record("doc-1")
    store.save_extraction(record)

    row = store.get_extraction("doc-1", "v1")
    assert row["url"] == "https://example.com/a"
    assert row["model"] == "gemini-2.5-flash-lite"
    assert row["extracted_json"] == '{"summary": {"value": "ok"}}'
    store.close()


def test_get_extraction_returns_none_when_missing(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    assert store.get_extraction("nope", "v1") is None
    store.close()


def test_save_extraction_upserts_on_rerun(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.save_extraction(_extraction_record("doc-1"))
    updated = _extraction_record("doc-1")
    updated.extracted_json = '{"summary": {"value": "revised"}}'
    store.save_extraction(updated)

    row = store.get_extraction("doc-1", "v1")
    assert row["extracted_json"] == '{"summary": {"value": "revised"}}'
    store.close()


def test_pages_without_extraction_excludes_already_extracted(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    rec_a = _record("https://example.com/a", content_hash="h1")
    rec_b = _record("https://example.com/b", content_hash="h2")
    store.upsert(rec_a, unchanged=False)
    store.upsert(rec_b, unchanged=False)

    doc_id_a = document_id_for("https://example.com/a")
    store.save_extraction(_extraction_record(doc_id_a))

    pending = store.pages_without_extraction("example.com", "v1")
    assert len(pending) == 1
    assert pending[0]["url"] == "https://example.com/b"
    store.close()
