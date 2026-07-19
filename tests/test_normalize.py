from crawler.normalize import normalize_url, registered_domain, resolve, same_site


def test_lowercases_scheme_and_host():
    assert normalize_url("https://EXAMPLE.com/Article") == "https://example.com/Article"


def test_drops_fragment():
    assert normalize_url("https://example.com/a#section") == "https://example.com/a"


def test_drops_tracking_params_but_keeps_meaningful_ones():
    result = normalize_url("https://example.com/a?page=2&utm_source=test&fbclid=abc")
    assert result == "https://example.com/a?page=2"


def test_sorts_query_params():
    result = normalize_url("https://example.com/a?b=2&a=1")
    assert result == "https://example.com/a?a=1&b=2"


def test_collapses_trailing_slash_except_root():
    assert normalize_url("https://example.com/a/") == "https://example.com/a"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_resolve_relative_href():
    assert resolve("https://example.com/dir/page", "../other") == "https://example.com/other"


def test_registered_domain_and_same_site():
    assert registered_domain("https://Example.com:8080/a") == "example.com"
    assert same_site("https://example.com/a", "https://example.com/b")
    assert not same_site("https://example.com/a", "https://other.com/b")
