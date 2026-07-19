from crawler.frontier import UrlFrontier


def test_seeds_with_depth_zero():
    frontier = UrlFrontier("https://example.com/", max_depth=3, max_pages=50)
    entry = frontier.pop()
    assert entry.url == "https://example.com/"
    assert entry.depth == 0


def test_rejects_cross_domain_links():
    frontier = UrlFrontier("https://example.com/", max_depth=3, max_pages=50)
    frontier.pop()
    added = frontier.add("https://other.com/page", depth=1)
    assert added is False
    assert len(frontier) == 0


def test_deduplicates_normalized_urls():
    frontier = UrlFrontier("https://example.com/", max_depth=3, max_pages=50)
    frontier.pop()
    first = frontier.add("https://example.com/a?utm_source=x", depth=1)
    second = frontier.add("https://example.com/a", depth=1)
    assert first is True
    assert second is False
    assert len(frontier) == 1


def test_respects_max_depth():
    frontier = UrlFrontier("https://example.com/", max_depth=1, max_pages=50)
    frontier.pop()
    added = frontier.add("https://example.com/too-deep", depth=2)
    assert added is False


def test_respects_max_pages_cap():
    frontier = UrlFrontier("https://example.com/", max_depth=5, max_pages=2)
    frontier.pop()  # visited_count -> 1, still under cap of 2
    added_first = frontier.add("https://example.com/a", depth=1)
    added_second = frontier.add("https://example.com/b", depth=1)
    assert added_first is True
    assert added_second is False  # 1 visited + 1 queued already == max_pages


def test_has_next_stops_at_page_cap():
    frontier = UrlFrontier("https://example.com/", max_depth=5, max_pages=1)
    assert frontier.has_next() is True
    frontier.pop()
    assert frontier.has_next() is False


def test_preseed_seen_skips_requeueing_already_done_seed():
    frontier = UrlFrontier(
        "https://example.com/",
        max_depth=3,
        max_pages=50,
        preseed_seen={"https://example.com/"},
    )
    assert frontier.has_next() is False
    assert len(frontier) == 0


def test_preseed_seen_does_not_block_other_urls():
    frontier = UrlFrontier(
        "https://example.com/",
        max_depth=3,
        max_pages=50,
        preseed_seen={"https://example.com/already-done"},
    )
    added = frontier.add("https://example.com/already-done", depth=1)
    assert added is False
    added_new = frontier.add("https://example.com/new-page", depth=1)
    assert added_new is True


def test_add_many_returns_accepted_urls_not_just_count():
    frontier = UrlFrontier("https://example.com/", max_depth=3, max_pages=50)
    frontier.pop()
    accepted = frontier.add_many(
        ["https://example.com/a", "https://other.com/b", "https://example.com/a"], depth=1
    )
    assert accepted == ["https://example.com/a"]
