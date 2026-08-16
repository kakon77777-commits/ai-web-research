"""Identity-preserving multi-cut search (IPMCS-lite) over this project's own
crawled corpus.

Ported from a real, already-working implementation — not a fresh design —
after Neo pointed at `IPMCS_v0.1_同一性多切面展開搜尋法_2026-08-15.md` and the
already-shipped IPMCS work in `unbounded-axiom` (`scripts/ipmcs/
ipmcs_search.mjs`, `shell/public/semantic/semantic-core.js`) and asked for
this project specifically ("這一個ai-web-research是做一個所有的搜尋法的") to be
where every search method lives, natively, not a thin client calling out to
another repo's MCP server ("這麼偷懶...也是反過來的").

What actually got ported vs. what's a genuine gap here, checked file-by-file
before writing a line of this module (not assumed from the paper's own
description):

- **Query divergence (D(q))** — not reimplemented, just reused: `diverge()`
  already existed in this project (`research.py`) before IPMCS existed at
  all, and unbounded-axiom's own IPMCS work already calls back INTO this
  same function via `diverge_cli.py`. `identity_search()` below calls the
  exact same `diverge()`.
- **Identity fold + candidate union + ranking** — the core IPMCS logic
  (group hits by canonical identity across every branch/retriever, rank
  has_exact-then-max_score) is genuinely corpus-agnostic and is ported
  faithfully from `ipmcs_search.mjs`'s `ipmcsSearch()`.
- **Exact/lexical scoring** — the ALGORITHM (`normalize_query`/`tokenize`/
  `trigrams`/token-overlap/trigram-overlap) is a direct port of
  `semantic-core.js`'s `normalizeQuery`/`tokenize`/`trigrams`/
  `scoreDocument`. The DOCUMENT SCHEMA it scores against is NOT ported —
  `semantic-core.js` scores a Logic Matrix paper's compact
  `{t: title, s: summary, h: headings, k: keywords}` record, which doesn't
  exist here. This module scores this project's own `pages` table instead
  (title + full crawled markdown), a genuinely different corpus with
  different characteristics (crawled full text, not curated paper
  metadata) — not a drop-in reuse, a real re-target.
- **Canonical identity** — didn't need inventing: `document_id_for(url)`
  (store.py) already is this project's stable per-URL identity key, doing
  exactly the job IPMCS's `paper_id` does for Logic Matrix.

Deliberately NOT ported, not faked to look present:
- **Semantic/embedding channel** — unbounded-axiom's version queries a
  specific Cloudflare Vectorize index built from Logic Matrix's own
  papers. This project has no vector index of its own crawled pages; a
  semantic channel here would need one built from scratch, not borrowed.
- **Multi-view segmentation (chunk-v1/changepoint-v1/etc.)** — every hit
  below is `view="document"` only. Matches the discipline the
  unbounded-axiom session itself used ("changepoint-v1 explicitly
  deferred — not fabricated, doesn't exist for this corpus yet") — this
  project has no chunk-level segmentation of its crawled markdown either.
- **ANLA-verified addressing** — unbounded-axiom's version resolves a
  paper_id against a specific pre-built 88MB `.anla` archive of Logic
  Matrix's own papers. Building an equivalent archive of THIS project's
  own corpus is a real, separate follow-up, not done here.

Given all of the above, `identity_search()`'s "identity recall" claim is
narrower than the full IPMCS paper's: query-divergence + exact/lexical +
identity-fold across whatever this project has actually crawled — real,
but not the semantic-channel rescue story unbounded-axiom's own C2
experiment demonstrated (that specifically needed the Vectorize channel
this module doesn't have).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .llm import LlmConfig, default_config_from_env
from .research import DivergenceSettings, diverge
from .store import PageStore

# Matches semantic-core.js's CJK_RE range (CJK Unified Ideographs block).
_CJK_RE = re.compile("[㐀-鿿]")
_LATIN_NUM_RE = re.compile(r"[a-z0-9+.\-]")

# Simpler than semantic-core.js's tiered weight table (that one was tuned
# for a specific curated-paper corpus with title/summary/heading/keyword
# fields and a 4-tier display system this project has no equivalent of) —
# three weights are enough to express "exact beats lexical, title beats
# body" without inventing tiers this corpus can't actually support.
WEIGHTS = {"exact_title": 1.0, "exact_content": 0.75, "lexical": 0.55}


def normalize_query(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(raw)).lower()).strip()


def _is_cjk(ch: str) -> bool:
    return bool(_CJK_RE.match(ch))


def tokenize(s: str) -> list[str]:
    """Latin/number runs become whole tokens; CJK (no word boundaries)
    becomes overlapping character bigrams — direct port of
    semantic-core.js's tokenize()."""
    tokens: list[str] = []
    buf = ""
    for ch in s:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
        elif _LATIN_NUM_RE.match(ch):
            buf += ch
        else:
            if buf:
                tokens.append(buf)
                buf = ""
    if buf:
        tokens.append(buf)
    cjk_only = [ch for ch in s if _is_cjk(ch)]
    for i in range(len(cjk_only) - 1):
        tokens.append(cjk_only[i] + cjk_only[i + 1])
    if len(cjk_only) == 1:
        tokens.append(cjk_only[0])
    return [t for t in tokens if t]


def trigrams(s: str) -> list[str]:
    chars = list(re.sub(r"\s+", "", s))
    if len(chars) < 3:
        return [("".join(chars))] if chars else []
    return ["".join(chars[i : i + 3]) for i in range(len(chars) - 2)]


def _overlap_ratio(query_items: list[str], doc_set: set[str]) -> float:
    if not query_items or not doc_set:
        return 0.0
    hit = sum(1 for t in query_items if t in doc_set)
    return hit / len(query_items)


@dataclass
class ScoredDocument:
    score: float
    channels: list[str]


def score_document(
    title_norm: str,
    content_norm: str,
    token_set: set[str],
    trigram_set: set[str],
    query_norm: str,
    query_tokens: list[str],
    query_trigrams: list[str],
) -> ScoredDocument:
    """Score one prepared document against one already-normalized query.
    Direct port of semantic-core.js's scoreDocument(), retargeted at this
    project's title+markdown-content schema instead of Logic Matrix's
    title/summary/headings/keywords schema."""
    channels: set[str] = set()
    best = 0.0

    if query_norm:
        if query_norm in title_norm:
            channels.add("exact")
            best = max(best, WEIGHTS["exact_title"])
        elif query_norm in content_norm:
            channels.add("exact")
            best = max(best, WEIGHTS["exact_content"])

    if query_tokens:
        ov = _overlap_ratio(query_tokens, token_set)
        if ov > 0:
            channels.add("lexical")
            best = max(best, WEIGHTS["lexical"] * ov)

    if "exact" not in channels and query_trigrams:
        ov = _overlap_ratio(query_trigrams, trigram_set)
        if ov > 0:
            channels.add("lexical")
            best = max(best, WEIGHTS["lexical"] * 0.7 * ov)

    return ScoredDocument(score=min(1.0, best), channels=sorted(channels))


@dataclass
class QueryBranch:
    type: str
    text: str


@dataclass
class SearchHit:
    view: str
    retriever: str
    branch_type: str
    branch_text: str
    score: float


@dataclass
class SearchObject:
    document_id: str
    url: str
    title: str | None
    has_exact: bool
    max_score: float
    paths: list[SearchHit] = field(default_factory=list)


@dataclass
class IdentitySearchResult:
    query: str
    branches: list[str]
    objects: list[SearchObject] = field(default_factory=list)
    per_branch: list[dict] = field(default_factory=list)


def _prepared_pages(store: PageStore) -> list[dict]:
    """Loads every crawled page's title + full markdown content (from disk,
    via the stored markdown_path — see store.py's upsert() for why that
    path can go missing on an unchanged re-crawl if the COALESCE fix there
    isn't in place) and precomputes normalized text + token/trigram sets
    once per document, not once per query branch."""
    prepared = []
    for row in store.all_pages():
        title = row["title"] or ""
        content = ""
        if row["markdown_path"]:
            try:
                content = Path(row["markdown_path"]).read_text(encoding="utf-8")
            except OSError:
                content = ""
        title_norm = normalize_query(title)
        content_norm = normalize_query(content)
        bag_norm = f"{title_norm} {content_norm}"
        prepared.append(
            {
                "document_id": row["document_id"],
                "url": row["url"],
                "title": row["title"],
                "title_norm": title_norm,
                "content_norm": content_norm,
                "token_set": set(tokenize(bag_norm)),
                "trigram_set": set(trigrams(bag_norm)),
            }
        )
    return prepared


async def _divergence_branches(
    seed_query: str,
    llm_config: LlmConfig | None,
    max_branches: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[QueryBranch]:
    """Flattens diverge()'s 5 DRC categories into IPMCS-style branches,
    original first, capped at max_branches beyond the original — same
    fan-out discipline as unbounded-axiom's own divergeBranches()."""
    branches = [QueryBranch("original", seed_query)]
    try:
        settings = DivergenceSettings(queries_per_category=1)
        result = await diverge(
            seed_query, llm_config or default_config_from_env(), settings=settings, client=client
        )
    except Exception:
        return branches
    seen = {seed_query}
    for category, queries in result.branches.items():
        for text in queries:
            if text in seen:
                continue
            seen.add(text)
            branches.append(QueryBranch(category, text))
            if len(branches) - 1 >= max_branches:
                return branches
    return branches


async def identity_search(
    seed_query: str,
    store: PageStore,
    llm_config: LlmConfig | None = None,
    *,
    use_divergence: bool = False,
    max_branches: int = 4,
    top_k: int = 10,
    client: httpx.AsyncClient | None = None,
) -> IdentitySearchResult:
    """Full IPMCS-lite loop over this project's own already-crawled corpus:
    optional query divergence -> exact/lexical scoring per branch over
    every page -> identity fold (group hits by document_id) -> rank
    (has_exact desc, then max_score desc). Pass use_divergence=True for a
    real LLM call per query (small, real cost, same as diverge()'s normal
    cost) generating alternate-phrasing branches; without it, only the
    original query text is scored. `client` is test-only plumbing (a mock
    httpx.AsyncClient) — the vertex provider path ignores it and always
    uses its own SDK client, same caveat as diverge()/basic_ai_search()."""
    branches = (
        await _divergence_branches(seed_query, llm_config, max_branches, client=client)
        if use_divergence
        else [QueryBranch("original", seed_query)]
    )

    docs = _prepared_pages(store)
    doc_by_id = {d["document_id"]: d for d in docs}
    object_hits: dict[str, list[SearchHit]] = {}
    per_branch: list[dict] = []

    for branch in branches:
        q_norm = normalize_query(branch.text)
        q_tokens = tokenize(q_norm)
        q_trigrams = trigrams(q_norm)
        branch_hit_count = 0
        for doc in docs:
            scored = score_document(
                doc["title_norm"], doc["content_norm"], doc["token_set"], doc["trigram_set"],
                q_norm, q_tokens, q_trigrams,
            )
            if scored.score > 0:
                branch_hit_count += 1
                for channel in scored.channels:
                    object_hits.setdefault(doc["document_id"], []).append(
                        SearchHit(
                            view="document", retriever=channel,
                            branch_type=branch.type, branch_text=branch.text, score=scored.score,
                        )
                    )
        per_branch.append({"branch_type": branch.type, "branch_text": branch.text, "hit_count": branch_hit_count})

    objects = []
    for document_id, paths in object_hits.items():
        doc = doc_by_id[document_id]
        has_exact = any(p.retriever == "exact" for p in paths)
        max_score = max(p.score for p in paths)
        objects.append(
            SearchObject(
                document_id=document_id, url=doc["url"], title=doc["title"],
                has_exact=has_exact, max_score=max_score, paths=paths,
            )
        )
    objects.sort(key=lambda o: (o.has_exact, o.max_score), reverse=True)

    return IdentitySearchResult(
        query=seed_query,
        branches=[b.type for b in branches],
        objects=objects[:top_k],
        per_branch=per_branch,
    )
