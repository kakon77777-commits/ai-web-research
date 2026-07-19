"""Deterministic URL normalization: N(u) = u'.

Only removes parameters that are known tracking noise. Never strips
arbitrary query params, since e.g. ?page=1 vs ?page=2 address different
content (see project doc, section 6.4).
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "igshid",
}


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in _TRACKING_PARAMS:
        return True
    return any(key_lower.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def resolve(base_url: str, href: str) -> str:
    """Resolve a possibly-relative href against a base URL."""
    return urljoin(base_url, href)


def normalize_url(url: str) -> str:
    """Apply deterministic normalization rules to a URL.

    - lowercase scheme and host
    - drop fragment
    - drop known tracking query params
    - sort remaining query params
    - collapse duplicate trailing slashes (but keep a single "/" for root)
    """
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    path = parsed.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)

    return urlunparse((scheme, netloc, path, "", query, ""))


def registered_domain(url: str) -> str:
    """Return the netloc (host[:port]) of a URL, lowercased, no credentials."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host.lower()


def same_site(url_a: str, url_b: str) -> bool:
    return registered_domain(url_a) == registered_domain(url_b)
