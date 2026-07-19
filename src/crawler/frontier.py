"""URL frontier: BFS queue with domain scoping, depth limit and page-count cap.

F_{t+1} = (F_t - {u_t}) union Links(u_t), constrained to same domain,
max_depth and max_pages (see project doc, section 6.1).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .normalize import normalize_url, registered_domain


@dataclass(frozen=True)
class FrontierEntry:
    url: str
    depth: int


def in_scope_url(
    url: str, seed_domain: str, depth: int, max_depth: int, same_domain_only: bool = True
) -> str | None:
    """Normalize and scope-check a discovered URL independent of any single
    run's page budget, so callers can persist the full to-do list even when
    the in-memory frontier for *this* run is already full."""
    if depth > max_depth:
        return None
    norm = normalize_url(url)
    if same_domain_only and registered_domain(norm) != seed_domain:
        return None
    return norm


class UrlFrontier:
    def __init__(
        self,
        seed_url: str,
        max_depth: int,
        max_pages: int,
        same_domain_only: bool = True,
        preseed_seen: set[str] | None = None,
    ):
        """preseed_seen marks URLs from a prior run as already handled (e.g.
        status 'done' in a persistent frontier store) so a resumed run skips
        re-queueing them without re-processing them."""
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self.seed_domain = registered_domain(seed_url)

        self._queue: deque[FrontierEntry] = deque()
        self._seen: set[str] = set(normalize_url(u) for u in preseed_seen) if preseed_seen else set()
        self._dequeued_count = 0

        self.add(seed_url, depth=0)

    def add(self, url: str, depth: int) -> bool:
        """Try to enqueue a URL. Returns True if it was added."""
        if depth > self.max_depth:
            return False
        if self._dequeued_count + len(self._queue) >= self.max_pages:
            return False

        norm = normalize_url(url)
        if norm in self._seen:
            return False
        if self.same_domain_only and registered_domain(norm) != self.seed_domain:
            return False

        self._seen.add(norm)
        self._queue.append(FrontierEntry(url=norm, depth=depth))
        return True

    def add_many(self, urls: list[str], depth: int) -> list[str]:
        """Returns the (normalized) URLs that were actually accepted, so
        callers can persist just the newly queued work."""
        accepted: list[str] = []
        for u in urls:
            if self.add(u, depth):
                accepted.append(normalize_url(u))
        return accepted

    def has_next(self) -> bool:
        return bool(self._queue) and self._dequeued_count < self.max_pages

    def pop(self) -> FrontierEntry:
        entry = self._queue.popleft()
        self._dequeued_count += 1
        return entry

    def __len__(self) -> int:
        return len(self._queue)

    @property
    def visited_count(self) -> int:
        return self._dequeued_count
