from pathlib import Path

from crawler.store import PageStore


def test_mark_pending_then_query_by_status(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.frontier_mark_pending("https://example.com/a", "example.com", 0, "t0")

    rows = store.frontier_urls_by_status("example.com", status="pending")
    assert rows == [("https://example.com/a", 0)]
    assert store.frontier_urls_by_status("example.com", status="done") == []
    store.close()


def test_mark_pending_is_idempotent(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.frontier_mark_pending("https://example.com/a", "example.com", 0, "t0")
    store.frontier_mark_pending("https://example.com/a", "example.com", 5, "t1")

    rows = store.frontier_urls_by_status("example.com", status="pending")
    assert rows == [("https://example.com/a", 0)]  # first insert wins, depth untouched
    store.close()


def test_mark_done_moves_url_between_status_buckets(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.frontier_mark_pending("https://example.com/a", "example.com", 0, "t0")
    store.frontier_mark_done("https://example.com/a", "t1")

    assert store.frontier_urls_by_status("example.com", status="pending") == []
    assert store.frontier_urls_by_status("example.com", status="done") == [
        ("https://example.com/a", 0)
    ]
    store.close()


def test_reset_domain_clears_only_that_domain(tmp_path: Path):
    store = PageStore(tmp_path / "crawl.db")
    store.frontier_mark_pending("https://example.com/a", "example.com", 0, "t0")
    store.frontier_mark_pending("https://other.com/a", "other.com", 0, "t0")

    store.frontier_reset_domain("example.com")

    assert store.frontier_urls_by_status("example.com", status="pending") == []
    assert store.frontier_urls_by_status("other.com", status="pending") == [
        ("https://other.com/a", 0)
    ]
    store.close()
