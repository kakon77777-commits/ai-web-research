"""MCP server exposing this project's crawl/extract/research capabilities
to any MCP host (Claude Desktop, Claude Code, other CHSA-aware agents),
per CHSA v0.2's positioning of MCP as an optional protocol/capability-
exchange layer over the search intelligence, not the intelligence itself
(`可組合混合搜尋架構技術白皮書_CHSA_v0.2_MCP補充版.md` §8: "MCP = Capability
Exchange Protocol ≠ Search Intelligence").

Tool names follow CHSA's suggested abstract profile (§8.7) where this
project's actual capabilities genuinely match it:
- `fetch_document`   ~ CHSA's fetch_document
- `extract_evidence` ~ CHSA's extract_evidence — this project's
  ExtractedField (value/source_quote/confidence/quote_verified) already
  matches CHSA's standard evidence-object shape (§9.2) almost field-for-
  field, so this mapping is a real one, not a stretch.
- `compile_research` ~ CHSA's compile_result

Deliberately NOT exposed, because they're not built (not faked to look
complete): `search_candidates` in the sense CHSA means it — a real LIVE
web-search API that could discover NEW candidate URLs this project has
never seen — is still unwired; `basic_ai_search` below is Neo's explicit
stand-in for it (whichever model `BASIC_SEARCH_MODEL` currently names —
gemini-3.7-flash as of 2026-08-16 — using its own prior knowledge,
tagged `llm_recall`, never confused with verified crawled evidence).
`identity_search_tool` is a DIFFERENT thing from `search_candidates`,
not a replacement for it — it searches this project's OWN
already-crawled corpus (real query divergence + exact/lexical scoring +
identity fold, ported 2026-08-16 from IPMCS v0.1, see
identity_search.py's own module docstring for exactly what was and
wasn't ported), never the open web. `resolve_versions` and
`get_relations` both need MRASG/SGCD-style graph engines, which remain
unbuilt — see project memory.

Stdio transport: this is a local Python CLI tool, not a hosted service
like [[project-ai-board]]'s Cloudflare Worker — stdio is the standard way
an MCP host (Claude Desktop, Claude Code) launches and talks to a local
tool process, not Streamable HTTP.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import load_config
from .identity_search import identity_search
from .llm import default_config_from_env
from .normalize import registered_domain
from .research import DivergenceSettings, basic_ai_search, compress, diverge, research_topic
from .run import crawl_site
from .semantic_extract import extract_site
from .store import PageStore

DEFAULT_CONFIG_PATH = Path("config/crawler.yaml")
DEFAULT_SCHEMA_PATH = Path("config/extraction_schema.example.json")

mcp = FastMCP(
    name="ai-web-research",
    instructions=(
        "Deterministic web crawler + LLM-driven semantic extraction and DRC "
        "(Divergence-Resonance-Compression) research agent. Fetches real "
        "pages (robots.txt-aware, SSRF-guarded), extracts structured "
        "evidence with independently-verified source quotes, and "
        "synthesizes multi-source findings into a cognitive-map research "
        "structure with hallucination-checked citations. No live web-search "
        "API is wired in — retrieval is bootstrapped from caller-supplied "
        "seed URLs, not autonomous search."
    ),
)


def _config():
    return load_config(DEFAULT_CONFIG_PATH)


@mcp.tool(
    description=(
        "Fetch a single URL (robots.txt-aware, SSRF-guarded) and store its "
        "raw HTML + Markdown. Does not follow links — for a full-site crawl, "
        "use the `crawler crawl` CLI command instead."
    ),
    annotations=ToolAnnotations(
        title="Fetch document",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def fetch_document(url: str) -> dict:
    config = _config()
    single_page_config = replace(config, crawler=replace(config.crawler, max_depth=0))
    stats = await crawl_site(url, single_page_config)
    return {
        "fetched": stats.fetched,
        "unchanged": stats.unchanged,
        "failed": stats.failed,
        "skipped_robots": stats.skipped_robots,
        "skipped_ssrf": stats.skipped_ssrf,
    }


@mcp.tool(
    description=(
        "Run LLM-driven structured extraction (Prompt-to-Extraction) against "
        "every already-fetched, not-yet-extracted page on a URL's domain. "
        "Every field's source_quote is independently verified against the "
        "page text before being trusted (quote_verified). schema_json "
        "overrides the default generic schema — pass a JSON Schema string: "
        '{"type":"object","properties":{"<name>":{"type":..., '
        '"description":...}, ...},"required":[...]}.'
    ),
    annotations=ToolAnnotations(
        title="Extract evidence",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def extract_evidence(url: str, schema_json: str | None = None) -> dict:
    config = _config()
    schema = (
        json.loads(schema_json)
        if schema_json
        else json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    domain = registered_domain(url)
    stats = await extract_site(domain, schema, config)
    return {
        "extracted": stats.extracted,
        "skipped_missing_markdown": stats.skipped_missing_markdown,
        "failed": stats.failed,
    }


@mcp.tool(
    description=(
        "DRC 'Divergence' step: generate search-query branches for a seed "
        "concept/question across five categories (semantic, task, source, "
        "language, perspective). Pure LLM call, no side effects — use this "
        "to plan which seed URLs to gather before calling research_topic."
    ),
    annotations=ToolAnnotations(
        title="Diverge queries",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def diverge_queries(seed: str, queries_per_category: int = 3) -> dict:
    settings = DivergenceSettings(queries_per_category=queries_per_category)
    result = await diverge(seed, default_config_from_env(), settings=settings)
    return {"seed": result.seed, "branches": result.branches}


@mcp.tool(
    description=(
        "Stand-in for a live web-search API, per Neo's explicit choice: forces "
        "gemini-3.7-flash (BASIC_SEARCH_MODEL) to answer from its own training "
        "knowledge for a set of queries, NOT live retrieval. Always tag/treat the "
        "result as source_type="
        "'llm_recall' (unverified prior knowledge, a lead worth checking, never "
        "presented as verified evidence) — this is exactly what research_topic "
        "does automatically for any branch with no seed URLs supplied."
    ),
    annotations=ToolAnnotations(
        title="Basic AI search (LLM recall)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def basic_ai_search_tool(seed: str, branch: str, queries_json: str) -> dict:
    queries = json.loads(queries_json)
    result = await basic_ai_search(seed, branch, queries, default_config_from_env())
    return {"branch": result.branch, "queries": result.queries, "answer": result.answer, "model": result.model}


@mcp.tool(
    description=(
        "DRC 'Compression' step (with GIPSS v0.2's counter-evidence-seeking and typed "
        "status folded in): synthesize a list of per-source findings into a cognitive-map "
        "structure (core_proposition, labeled clusters each with a status of "
        "well_supported/partially_supported/contradicted/insufficient_evidence, "
        "source_urls, next_queries prioritizing falsification, unresolved_conflicts). "
        'findings_json is a JSON array of {"url":..., "source_type": "web_crawled"|'
        '"llm_recall", "key_claim":..., "stance":..., "relevance":...} objects — '
        "source_type matters: web_crawled is independently-verified page evidence, "
        "llm_recall is unverified model prior knowledge (used only when no seed URL was "
        "supplied for a branch) and is treated as a lower-confidence lead, never as "
        "verified evidence. Every cited source_url is checked against the findings "
        "actually given — unrecognized URLs are dropped and reported in "
        "validation_errors, never silently trusted."
    ),
    annotations=ToolAnnotations(
        title="Compile research",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def compile_research(seed: str, findings_json: str) -> dict:
    findings = json.loads(findings_json)
    result = await compress(seed, findings, default_config_from_env())
    return result.to_dict()


@mcp.tool(
    description=(
        "Full DRC research loop: diverge -> fetch each caller-supplied seed "
        "URL per branch -> extract structured evidence -> compress into a "
        "research map. seed_urls_by_branch_json is a JSON object "
        '{"branch_label": ["https://...", ...], ...}. No live web search is '
        "wired in — seed URLs must be supplied by the caller; use "
        "diverge_queries first to help pick what to search for elsewhere, "
        "then pass the resulting URLs here. Any branch with no seed URLs "
        "supplied automatically falls back to gemini-3.7-flash's own prior "
        "knowledge as a 'basic AI search' stand-in (tagged source_type="
        "'llm_recall' in the findings that feed compression, never "
        "conflated with verified web-crawled evidence) — pass "
        "use_llm_recall_fallback=false to disable this and skip empty "
        "branches entirely instead."
    ),
    annotations=ToolAnnotations(
        title="Research topic",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def research_topic_tool(
    seed: str, seed_urls_by_branch_json: str, use_llm_recall_fallback: bool = True
) -> dict:
    seed_urls_by_branch = json.loads(seed_urls_by_branch_json)
    run = await research_topic(
        seed, seed_urls_by_branch, _config(), use_llm_recall_fallback=use_llm_recall_fallback
    )
    return {
        "run_id": run.id,
        "seed": run.seed,
        "branches": run.branches,
        "compression": run.compression,
    }


@mcp.tool(
    description=(
        "Identity-preserving multi-cut search (IPMCS-lite) over THIS PROJECT'S "
        "OWN already-crawled corpus (the `pages` table) — not the open web, and "
        "not a replacement for search_candidates/basic_ai_search. Scores every "
        "crawled page by exact-match + lexical (token/trigram) overlap, folds "
        "hits that land on the same document_id across query branches into one "
        "ranked object (has_exact desc, then max_score desc). Ported 2026-08-16 "
        "from IPMCS v0.1 / unbounded-axiom's ipmcs_search.mjs — see "
        "identity_search.py's module docstring for the exact line between what "
        "was ported (query-divergence reuse, identity-fold+ranking, exact/"
        "lexical scoring algorithm) and what's deliberately NOT here yet (no "
        "semantic/Vectorize channel, no multi-view chunk segmentation, no "
        "ANLA-verified addressing — every hit is view='document' only). Pass "
        "use_divergence=true for a real, small-cost LLM call generating "
        "alternate-phrasing query branches before scoring; without it, only "
        "the literal query text is scored."
    ),
    annotations=ToolAnnotations(
        title="Identity search (own corpus)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def identity_search_tool(query: str, use_divergence: bool = False, top_k: int = 10) -> dict:
    config = _config()
    store = PageStore(config.storage.db_path)
    try:
        result = await identity_search(query, store, use_divergence=use_divergence, top_k=top_k)
    finally:
        store.close()
    return {
        "query": result.query,
        "branches": result.branches,
        "per_branch": result.per_branch,
        "objects": [asdict(o) for o in result.objects],
    }


@mcp.tool(
    description="Retrieve a previously persisted research run by its id.",
    annotations=ToolAnnotations(
        title="Get research run",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def get_research_run(run_id: int) -> dict:
    config = _config()
    store = PageStore(config.storage.db_path)
    try:
        row = store.get_research_run(run_id)
    finally:
        store.close()
    if row is None:
        return {"found": False}
    return {
        "found": True,
        "seed": row["seed"],
        "branches": json.loads(row["branches_json"]),
        "compression": json.loads(row["compression_json"]),
        "created_at": row["created_at"],
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
