"""Research agent (doc1 第十二部分, 階段五：研究 Agent) — built on the DRC
Search loop (Divergence–Resonance–Compression, `drc_search_whitepaper_v0_1.md`)
instead of doc1's own placeholder suggestion (GPT Researcher / Open Deep
Research). Neo asked to fold DRC in now rather than build the simpler
version first and redo it later once the whitepaper landed.

Scope actually shipped vs. the full DRC vision, disclosed here rather than
silently glossed over: this project has no live web-search API (no Exa/
Tavily/Brave/Google Custom Search key configured anywhere) — only a crawler
that fetches URLs it's given. So:

- `diverge()` (query-branch generation, DRC doc §3.2's five categories) is
  real and complete on its own — it needs nothing but an LLM call.
- The "multi-source retrieval" step of the DRC Crawler pattern (DRC doc
  Ch.8) is bootstrapped from CALLER-SUPPLIED seed URLs per branch, not
  autonomous open-web search. `research_topic()` fetches exactly those
  URLs (via the existing `crawl_site()`, bounded to depth 0 — a research
  seed is a specific page, not a whole site to BFS-crawl) and runs Stage 4
  extraction against them with a research-oriented schema. Wiring a real
  search API in later is a drop-in replacement for "how do the seed URLs
  get chosen" — everything downstream (extraction, compression) is
  unaffected by that change.
- "Resonance" scoring (DRC doc Ch.4's multi-factor relevance ranking) is
  NOT implemented as a separate scored/ranked step — with caller-supplied
  seeds there's no large candidate pool to rank down, and extraction's own
  `stance`/`relevance` fields already carry the signal `compress()` needs.
  Revisit if/when a real search API produces a large candidate set that
  actually needs filtering before compression.

MRASG (the multi-resolution argument-graph doc DRC pairs with, and VRCA's
own theoretical unification of both) is deliberately NOT built here — its
own MVP section (§15) scopes it as a standalone graph-storage engine, a
separably large piece, not a bolt-on to this crawler.

2026-07-25 update, folding in two further whitepapers (GIPE v0.1 "全域欲相位
認識論" and GIPSS v0.2 "全域欲相位語義搜尋法"/DRC+SGCD unification) — scoped
narrowly, not the full theory:

- GIPE's own scope (physical experiments, DFT, chemistry synthesis, formal
  proof engines, lab-in-the-loop) is far beyond a web crawler and is NOT
  attempted here. What DOES transfer directly: GIPE's epistemic-action
  framing treats "query a model's own prior knowledge" as one valid
  epistemic action among many (查詢/閱讀/計算/模擬/測量/實驗/...), distinct
  from live retrieval and never to be disguised as verified evidence
  ("推論不能偽裝成原始證據"). `basic_ai_search()` implements exactly that
  one action — nothing more.
- GIPSS v0.2's SGCD (a full dynamic semantic graph with typed multi-
  dimensional coupling vectors) is the same class of large, separate
  graph-engine effort as MRASG — also NOT built here.
- Two ideas from GIPSS v0.2 DO fold cleanly into the existing compress()
  step without new infrastructure: counter-evidence-seeking (反證優先 — a
  finding that could overturn the emerging conclusion is worth more than
  one more confirming example) and typed/multi-level support status
  instead of a single score (缺失值不是零 — "not found," "contradicted,"
  and "confirmed" are different situations). Both are now in
  `compress()`'s prompt and `CompressionCluster.status`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field, replace

import httpx

from .config import AppConfig
from .llm import LlmConfig, complete, default_config_from_env, vertex_config_from_env
from .normalize import registered_domain
from .run import crawl_site
from .semantic_extract import (
    ExtractionError,
    _parse_llm_json,
    extract_site,
    schema_extractor_version,
)
from .store import PageStore, ResearchRunRecord, document_id_for

logger = logging.getLogger("crawler.research")

# Internal contract with compress() — not exposed as a swappable CLI schema
# like extract's default, since compress()'s prompt hard-depends on these
# exact field names.
RESEARCH_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "key_claim": {
            "type": "string",
            "description": "The single most important claim or fact this page contributes toward the research topic.",
        },
        "stance": {
            "type": "string",
            "enum": ["supports", "opposes", "neutral", "informational"],
            "description": "Whether this page's content supports, opposes, or is neutral/informational relative to the research topic.",
        },
        "relevance": {
            "type": "string",
            "description": "One sentence on why this page is relevant to the research topic.",
        },
        "notable_quote": {
            "type": "string",
            "description": "A short direct quote from the page worth citing.",
        },
    },
    "required": ["key_claim", "stance", "relevance"],
}

DEFAULT_DIVERGENCE_CATEGORIES = ("semantic", "task", "source", "language", "perspective")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# -- Divergence (DRC doc §3.2, Ch.10.2.2) ------------------------------------


@dataclass
class DivergenceSettings:
    categories: tuple[str, ...] = DEFAULT_DIVERGENCE_CATEGORIES
    queries_per_category: int = 3
    languages: tuple[str, ...] = ("English", "Traditional Chinese")


@dataclass
class DivergenceResult:
    seed: str
    branches: dict[str, list[str]] = field(default_factory=dict)


_DIVERGENCE_CATEGORY_MEANING = {
    "semantic": "synonyms and closely related concepts",
    "task": "queries oriented toward the user's likely underlying goal, e.g. competitors, "
    "open-source alternatives, business model, legal risk, technical architecture",
    "source": "queries tailored to specific source types: GitHub, official documentation, "
    "academic papers, forums",
    "language": "the same core concept translated into other languages, to surface "
    "language-specific results",
    "perspective": "the same topic approached from different viewpoints: engineering, "
    "business, legal, UX, academic",
}


def _divergence_system_prompt(settings: DivergenceSettings) -> str:
    category_lines = "\n".join(
        f'- "{c}": {_DIVERGENCE_CATEGORY_MEANING.get(c, "")}' for c in settings.categories
    )
    return (
        "You are a research query-expansion engine implementing the 'Divergence' step of a "
        "Divergence-Resonance-Compression (DRC) search method. Given a seed concept or "
        f"question, generate about {settings.queries_per_category} concrete search query "
        "strings for EACH of the following categories:\n"
        f"{category_lines}\n\n"
        'Respond with ONLY a single JSON object: {"branches": {"<category>": ["<query>", ...], '
        "...}} — one key per category listed above, each value an array of actual query "
        "strings (not descriptions of what to search for)."
    )


def _divergence_user_prompt(seed: str, settings: DivergenceSettings) -> str:
    lang_hint = ""
    if "language" in settings.categories:
        lang_hint = f"\nFor the \"language\" category, translate into: {', '.join(settings.languages)}."
    return f"Seed concept/question: {seed}{lang_hint}"


async def diverge(
    seed: str,
    llm_config: LlmConfig,
    *,
    settings: DivergenceSettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> DivergenceResult:
    """Generates search-query branches across DRC's five divergence
    categories (DRC doc §3.2) — the 問題分解 half of doc1's Stage 5."""
    settings = settings or DivergenceSettings()
    raw = await complete(
        llm_config,
        _divergence_user_prompt(seed, settings),
        system=_divergence_system_prompt(settings),
        client=client,
    )
    data = _parse_llm_json(raw)
    branches_raw = data.get("branches", {})

    branches: dict[str, list[str]] = {}
    for category in settings.categories:
        queries = branches_raw.get(category)
        if isinstance(queries, list):
            branches[category] = [str(q) for q in queries if q]
    return DivergenceResult(seed=seed, branches=branches)


# -- LLM recall: a "basic AI search" stand-in (GIPE 附錄A, one epistemic
# action among many) -----------------------------------------------------

BASIC_SEARCH_MODEL = "gemini-3.7-flash"


@dataclass
class RecallFinding:
    branch: str
    queries: list[str]
    answer: str
    model: str


def _recall_system_prompt() -> str:
    return (
        "You are acting as a basic AI search stand-in — NOT a live web search. Given a "
        "set of search-style queries for one branch of a research topic, answer with "
        "what you already know from training, as concisely and factually as you can. If "
        "you are not confident, or your knowledge may be outdated or incomplete, say so "
        'explicitly rather than guessing. Respond with ONLY a single JSON object: '
        '{"answer": "...", "confidence": "high"|"medium"|"low", "caveat": "..." (empty '
        'string if none)}.'
    )


def _recall_user_prompt(seed: str, branch: str, queries: list[str]) -> str:
    query_lines = "\n".join(f"- {q}" for q in queries)
    return f"Research topic: {seed}\nBranch: {branch}\nQueries:\n{query_lines}"


def basic_search_llm_config(base: LlmConfig | None = None) -> LlmConfig:
    """Forces the 'basic AI search' stand-in role onto whatever model
    BASIC_SEARCH_MODEL currently names, via Vertex specifically —
    regardless of whatever model the caller's default LlmConfig otherwise
    points at (extraction/compression may reasonably use a different/
    cheaper model for their own purposes). Named model-agnostically
    (not e.g. `gemini_35_flash_config`) because this is Neo's second
    swap of BASIC_SEARCH_MODEL already (3.5-flash on 2026-07-25 ->
    3.7-flash on 2026-08-16, "先把AI模型改成GEMINI3.7...之後要加新的搜尋法" —
    framed as a placeholder pending real search-API research, not a
    settled choice) — a version-specific function name would just need
    renaming again at the next swap.

    Forces vertex_location='global' regardless of VERTEX_LOCATION (which
    defaults to us-central1): confirmed live for gemini-3.5-flash that it
    404s in us-central1 for this project but works in 'global' (same
    region-availability gap already found for Claude on Vertex), and
    re-confirmed live for gemini-3.7-flash specifically before this swap
    shipped — not assumed to carry over just because the model name looks
    similar. Also forces max_tokens up to 4096: confirmed live for
    gemini-3.5-flash that this model family spends part of its output
    budget on internal reasoning before emitting visible text, so a small
    budget either returns empty text (finish_reason=MAX_TOKENS with no
    content at all) or truncates a real JSON-wrapped answer mid-string —
    1024 was enough for a one-word test reply but not an actual
    substantive search-style answer. gemini-3.7-flash live-verified to
    need the same 4096 floor via basic_ai_search() itself, not just a
    trivial "say OK" call, before trusting this budget for it too."""
    base = base or default_config_from_env()
    if base.provider != "vertex":
        vertex_cfg = vertex_config_from_env()
        if vertex_cfg is not None:
            base = vertex_cfg
    if base.provider == "vertex":
        return replace(base, model=BASIC_SEARCH_MODEL, vertex_location="global", max_tokens=4096)
    return replace(base, model=BASIC_SEARCH_MODEL, max_tokens=4096)


async def basic_ai_search(
    seed: str,
    branch: str,
    queries: list[str],
    llm_config: LlmConfig | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> RecallFinding:
    """Stand-in for a real web-search API, per Neo: 搜尋引擎API還沒去用跟研究,
    先調用 Gemini Flash 充當,讓他們去當基本的AI搜尋 — the exact model is
    whatever BASIC_SEARCH_MODEL currently names (3.5-flash on 2026-07-25,
    3.7-flash on 2026-08-16). This is the model's own prior/training
    knowledge, NOT live retrieval — GIPE's own principle
    ("推論不能偽裝成原始證據", model inference must never be disguised as
    raw evidence) means every result from this function is tagged
    source_type='llm_recall' by its caller, kept structurally distinct
    from Stage 4's verified, quote-checked web-crawled evidence. Swap in a
    real search API later by adding a branch in research_topic() that
    returns real URLs to crawl instead of calling this — nothing else
    changes."""
    cfg = basic_search_llm_config(llm_config)
    raw = await complete(
        cfg, _recall_user_prompt(seed, branch, queries), system=_recall_system_prompt(), client=client
    )
    data = _parse_llm_json(raw)
    return RecallFinding(branch=branch, queries=queries, answer=str(data.get("answer", "")), model=cfg.model)


# -- Compression (DRC doc §5, Ch.10.2.6-10.2.7) ------------------------------


STATUS_VALUES = ("well_supported", "partially_supported", "contradicted", "insufficient_evidence")


@dataclass
class CompressionCluster:
    label: str
    summary: str
    status: str = ""
    source_urls: list[str] = field(default_factory=list)


@dataclass
class CompressionResult:
    core_proposition: str
    clusters: list[CompressionCluster] = field(default_factory=list)
    next_queries: list[str] = field(default_factory=list)
    unresolved_conflicts: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "core_proposition": self.core_proposition,
            "clusters": [
                {"label": c.label, "summary": c.summary, "status": c.status, "source_urls": c.source_urls}
                for c in self.clusters
            ],
            "next_queries": self.next_queries,
            "unresolved_conflicts": self.unresolved_conflicts,
            "validation_errors": self.validation_errors,
        }


def _compression_system_prompt() -> str:
    return (
        "You are a research synthesis engine implementing the 'Compression' step of a "
        "Divergence-Resonance-Compression (DRC) search method, extended with two "
        "principles from a companion theory (GIPSS v0.2, 反證優先 and typed discovery "
        "status): (1) actively look for findings that CONTRADICT the emerging core "
        "proposition, not just ones that confirm it — a finding that would overturn your "
        "current best answer is more valuable than one more confirming example; (2) "
        "classify each cluster's support using multiple levels rather than a single "
        "score, since 'not found', 'confirmed false', and 'contradicted by other "
        "sources' are different situations, not all equivalent to zero.\n\n"
        "You will be given a research seed topic and a list of findings from multiple "
        "sources — each has a URL, a source_type ('web_crawled' for independently-"
        "verified page evidence with checked source quotes, or 'llm_recall' for a "
        "model's own unverified prior knowledge used only because no live search API is "
        "configured — treat llm_recall findings as lower-confidence leads, never as "
        "verified evidence), a key claim, stance, and relevance.\n\n"
        'Respond with ONLY a single JSON object with these keys: "core_proposition" (one '
        'sentence capturing the central finding across all sources), "clusters" (an array '
        'of objects, each with "label" a short cluster name, "summary" a 1-3 sentence '
        f'synthesis, "status" one of {list(STATUS_VALUES)!r}, and "source_urls" an array '
        "of URLs from the given findings that belong to this cluster — you MUST only use "
        'URLs that were actually given to you in the findings list, never invent one), '
        '"next_queries" (an array of 3-6 suggested follow-up search queries, prioritizing '
        'ones that could falsify the core_proposition rather than just confirm it), and '
        '"unresolved_conflicts" (an array of strings describing any contradictions found '
        "between sources, or an empty array if none)."
    )


def _compression_user_prompt(seed: str, findings: list[dict]) -> str:
    return (
        f"Research seed topic: {seed}\n\n"
        f"Findings (JSON):\n{json.dumps(findings, ensure_ascii=False, indent=2)}"
    )


async def compress(
    seed: str,
    findings: list[dict],
    llm_config: LlmConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> CompressionResult:
    """Synthesizes per-page findings into a cognitive-map-style structure
    (DRC doc §5.2-5.3) — every cited source_url is independently verified
    against the findings actually given, the same anti-hallucination
    discipline semantic_extract.py applies to source_quote (DRC doc's own
    principle: 'AI 可以壓縮，但不能切斷來源')."""
    known_urls = {f["url"] for f in findings if f.get("url")}
    raw = await complete(
        llm_config,
        _compression_user_prompt(seed, findings),
        system=_compression_system_prompt(),
        client=client,
    )
    data = _parse_llm_json(raw)

    errors: list[str] = []
    clusters: list[CompressionCluster] = []
    for c in data.get("clusters", []) or []:
        if not isinstance(c, dict):
            continue
        urls = [u for u in (c.get("source_urls") or []) if isinstance(u, str)]
        unknown = [u for u in urls if u not in known_urls]
        if unknown:
            errors.append(f"cluster {c.get('label')!r} cites URLs not in findings: {unknown}")
        status = str(c.get("status", ""))
        if status not in STATUS_VALUES:
            errors.append(f"cluster {c.get('label')!r} has non-standard status {status!r}")
        clusters.append(
            CompressionCluster(
                label=str(c.get("label", "")),
                summary=str(c.get("summary", "")),
                status=status,
                source_urls=[u for u in urls if u in known_urls],
            )
        )

    return CompressionResult(
        core_proposition=str(data.get("core_proposition", "")),
        clusters=clusters,
        next_queries=[str(q) for q in (data.get("next_queries") or [])],
        unresolved_conflicts=[str(c) for c in (data.get("unresolved_conflicts") or [])],
        validation_errors=errors,
    )


# -- Orchestrator -------------------------------------------------------------


@dataclass
class ResearchRun:
    id: int | None
    seed: str
    branches: dict[str, list[str]]
    compression: dict


async def research_topic(
    seed: str,
    seed_urls_by_branch: dict[str, list[str]],
    config: AppConfig,
    llm_config: LlmConfig | None = None,
    divergence_settings: DivergenceSettings | None = None,
    use_llm_recall_fallback: bool = True,
) -> ResearchRun:
    """Full DRC loop bootstrapped from caller-supplied seed URLs (see module
    docstring for why there's no live search step yet):
    diverge() labels the research question -> crawl_site() fetches each
    caller-supplied seed at depth 0 (single page, not a site BFS) ->
    extract_site() (Stage 4) pulls key_claim/stance/relevance per page ->
    compress() synthesizes across all of it into a cognitive-map structure.

    Any branch diverge() produced that the caller gave NO seed URLs for
    falls back to basic_ai_search() (gemini-3.5-flash 'basic AI search'
    stand-in) instead of being silently skipped — pass
    use_llm_recall_fallback=False to disable this and only use real
    caller-supplied evidence. Every finding is tagged source_type
    ('web_crawled' vs 'llm_recall') so compress() — and anything reading
    the persisted run later — can tell verified evidence from recalled
    prior knowledge apart; they are never merged into one undifferentiated
    pile.

    Persists the run (branches + compression) to `research_runs` for later
    retrieval."""
    if llm_config is None:
        llm_config = default_config_from_env()

    divergence = await diverge(seed, llm_config, settings=divergence_settings)

    # A research seed is one specific page (arXiv paper, GitHub repo, doc
    # page) — max_depth=0 bounds crawl_site() to fetching just that URL,
    # not BFS-crawling the whole site it lives on.
    single_page_config = replace(config, crawler=replace(config.crawler, max_depth=0))

    domains_crawled: set[str] = set()
    for urls in seed_urls_by_branch.values():
        for url in urls:
            try:
                await crawl_site(url, single_page_config)
            except Exception:
                logger.warning("failed to crawl seed URL %s", url, exc_info=True)
                continue
            domains_crawled.add(registered_domain(url))

    for domain in domains_crawled:
        try:
            await extract_site(domain, RESEARCH_EXTRACTION_SCHEMA, config, llm_config)
        except ExtractionError:
            logger.warning("extraction failed for domain %s", domain, exc_info=True)

    research_version = schema_extractor_version(RESEARCH_EXTRACTION_SCHEMA)
    findings: list[dict] = []
    store = PageStore(config.storage.db_path)
    try:
        for branch, urls in seed_urls_by_branch.items():
            for url in urls:
                row = store.get_extraction(document_id_for(url), research_version)
                if row is None:
                    continue
                data = json.loads(row["extracted_json"])
                findings.append(
                    {
                        "branch": branch,
                        "url": url,
                        "source_type": "web_crawled",
                        "key_claim": (data.get("key_claim") or {}).get("value"),
                        "stance": (data.get("stance") or {}).get("value"),
                        "relevance": (data.get("relevance") or {}).get("value"),
                    }
                )

        if use_llm_recall_fallback:
            for branch, queries in divergence.branches.items():
                if seed_urls_by_branch.get(branch) or not queries:
                    continue  # branch already has real crawled findings, or nothing to recall
                try:
                    recall = await basic_ai_search(seed, branch, queries, llm_config)
                except Exception:
                    logger.warning("llm recall failed for branch %s", branch, exc_info=True)
                    continue
                findings.append(
                    {
                        "branch": branch,
                        "url": f"llm-recall://{branch}",
                        "source_type": "llm_recall",
                        "key_claim": recall.answer,
                        "stance": "informational",
                        "relevance": (
                            f"Model prior-knowledge recall ({recall.model}) for branch "
                            f"'{branch}' — no live search API configured, no seed URLs "
                            "supplied for this branch."
                        ),
                    }
                )

        compression = await compress(seed, findings, llm_config)

        run_id = store.save_research_run(
            ResearchRunRecord(
                seed=seed,
                branches_json=json.dumps(divergence.branches, ensure_ascii=False),
                compression_json=json.dumps(compression.to_dict(), ensure_ascii=False),
                created_at=_now(),
            )
        )
    finally:
        store.close()

    return ResearchRun(
        id=run_id, seed=seed, branches=divergence.branches, compression=compression.to_dict()
    )
