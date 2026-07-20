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
complete): `search_candidates` (no live search API — see research.py's own
docstring for why), `resolve_versions` and `get_relations` (both need
MRASG, which remains unbuilt — see project memory).

Stdio transport: this is a local Python CLI tool, not a hosted service
like [[project-ai-board]]'s Cloudflare Worker — stdio is the standard way
an MCP host (Claude Desktop, Claude Code) launches and talks to a local
tool process, not Streamable HTTP.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import load_config
from .llm import default_config_from_env
from .normalize import registered_domain
from .research import DivergenceSettings, compress, diverge, research_topic
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
        "DRC 'Compression' step: synthesize a list of per-page findings into "
        "a cognitive-map structure (core_proposition, labeled clusters with "
        "source_urls, next_queries, unresolved_conflicts). findings_json is "
        'a JSON array of {"url":..., "key_claim":..., "stance":..., '
        '"relevance":...} objects. Every cited source_url is checked against '
        "the findings actually given — unrecognized URLs are dropped and "
        "reported in validation_errors, never silently trusted."
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
        "then pass the resulting URLs here."
    ),
    annotations=ToolAnnotations(
        title="Research topic",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def research_topic_tool(seed: str, seed_urls_by_branch_json: str) -> dict:
    seed_urls_by_branch = json.loads(seed_urls_by_branch_json)
    run = await research_topic(seed, seed_urls_by_branch, _config())
    return {
        "run_id": run.id,
        "seed": run.seed,
        "branches": run.branches,
        "compression": run.compression,
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
