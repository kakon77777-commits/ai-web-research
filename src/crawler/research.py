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
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field, replace

import httpx

from .config import AppConfig
from .llm import LlmConfig, complete, default_config_from_env
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


# -- Compression (DRC doc §5, Ch.10.2.6-10.2.7) ------------------------------


@dataclass
class CompressionCluster:
    label: str
    summary: str
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
                {"label": c.label, "summary": c.summary, "source_urls": c.source_urls}
                for c in self.clusters
            ],
            "next_queries": self.next_queries,
            "unresolved_conflicts": self.unresolved_conflicts,
            "validation_errors": self.validation_errors,
        }


def _compression_system_prompt() -> str:
    return (
        "You are a research synthesis engine implementing the 'Compression' step of a "
        "Divergence-Resonance-Compression (DRC) search method. You will be given a research "
        "seed topic and a list of extracted findings from multiple source pages (each with a "
        "URL, key claim, stance, and relevance). Synthesize these into a structured research "
        'map. Respond with ONLY a single JSON object with these keys: "core_proposition" (one '
        'sentence capturing the central finding across all sources), "clusters" (an array of '
        'objects, each with "label" a short cluster name, "summary" a 1-3 sentence synthesis, '
        'and "source_urls" an array of URLs from the given findings that belong to this '
        "cluster — you MUST only use URLs that were actually given to you in the findings "
        'list, never invent one), "next_queries" (an array of 3-6 suggested follow-up search '
        'queries for the next research round), and "unresolved_conflicts" (an array of '
        "strings describing any contradictions found between sources, or an empty array if "
        "none)."
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
        clusters.append(
            CompressionCluster(
                label=str(c.get("label", "")),
                summary=str(c.get("summary", "")),
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
) -> ResearchRun:
    """Full DRC loop bootstrapped from caller-supplied seed URLs (see module
    docstring for why there's no live search step yet):
    diverge() labels the research question -> crawl_site() fetches each
    caller-supplied seed at depth 0 (single page, not a site BFS) ->
    extract_site() (Stage 4) pulls key_claim/stance/relevance per page ->
    compress() synthesizes across all of it into a cognitive-map structure.
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
                        "key_claim": (data.get("key_claim") or {}).get("value"),
                        "stance": (data.get("stance") or {}).get("value"),
                        "relevance": (data.get("relevance") or {}).get("value"),
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
