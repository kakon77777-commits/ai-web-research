"""Standalone manual verification for src/crawler/mcp_server.py — spawns the
real server as a subprocess and drives it with a real MCP client over
stdio, calling every tool for real (not mocked).

Deliberately NOT wired into `pytest -q` — matches the precedent already set
for ai-board's own MCP server (`verify-remote-mcp.mjs`, a standalone script
rather than a pytest-integrated test): spawning + tearing down a subprocess
on every fast-suite run risks flakiness/leaked processes for marginal
coverage gain over a manually-run end-to-end check.

Usage:
    .venv/Scripts/python.exe scripts/verify_mcp_server.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent


async def main() -> int:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "crawler.mcp_server"],
        cwd=str(REPO_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"tools: {names}")
            expected = {
                "fetch_document",
                "extract_evidence",
                "diverge_queries",
                "compile_research",
                "research_topic_tool",
                "get_research_run",
            }
            assert expected.issubset(set(names)), f"missing tools: {expected - set(names)}"

            print("\n--- fetch_document(https://example.com/) ---")
            result = await session.call_tool("fetch_document", {"url": "https://example.com/"})
            print(result.content[0].text)

            print("\n--- extract_evidence(https://example.com/) ---")
            result = await session.call_tool("extract_evidence", {"url": "https://example.com/"})
            print(result.content[0].text)

            print("\n--- diverge_queries('AI-native Markdown editors') ---")
            result = await session.call_tool(
                "diverge_queries", {"seed": "AI-native Markdown editors", "queries_per_category": 2}
            )
            divergence = json.loads(result.content[0].text)
            print(json.dumps(divergence, indent=2, ensure_ascii=False))
            assert divergence["branches"], "diverge_queries returned no branches"

            print("\n--- compile_research (synthetic findings) ---")
            findings = [
                {
                    "url": "https://example.com/",
                    "key_claim": "Example.com is a reserved documentation domain.",
                    "stance": "informational",
                    "relevance": "Baseline placeholder domain.",
                }
            ]
            result = await session.call_tool(
                "compile_research",
                {"seed": "documentation placeholder domains", "findings_json": json.dumps(findings)},
            )
            compression = json.loads(result.content[0].text)
            print(json.dumps(compression, indent=2, ensure_ascii=False))
            assert compression["validation_errors"] == [], "unexpected validation errors"

            print("\n--- research_topic_tool (real seed URLs) ---")
            seeds = {"technical": ["https://example.com/"]}
            result = await session.call_tool(
                "research_topic_tool",
                {
                    "seed": "documentation placeholder domains",
                    "seed_urls_by_branch_json": json.dumps(seeds),
                },
            )
            research = json.loads(result.content[0].text)
            print(json.dumps(research, indent=2, ensure_ascii=False))
            run_id = research["run_id"]
            assert run_id is not None, "research_topic_tool did not return a run_id"

            print(f"\n--- get_research_run({run_id}) ---")
            result = await session.call_tool("get_research_run", {"run_id": run_id})
            fetched_run = json.loads(result.content[0].text)
            print(json.dumps(fetched_run, indent=2, ensure_ascii=False))
            assert fetched_run["found"] is True
            assert fetched_run["seed"] == "documentation placeholder domains"

    print("\n[SUCCESS] all MCP tools round-tripped correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
