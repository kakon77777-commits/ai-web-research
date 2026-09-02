"""Standalone manual verification for the Vertex-flavored Gemini Google
Search provider — same precedent as verify_brave_search_provider.py, not
wired into `pytest -q` (a real Vertex round-trip is a live network call, not
a fast-suite unit test).

Reuses this project's existing Vertex config (VERTEX_PROJECT_ID +
VERTEX_CREDENTIALS_PATH in .env) — no separate credential needed, since this
provider is deliberately built on the same service-account path
src/crawler/llm.py already uses.

Usage:
    .venv/Scripts/python.exe scripts/verify_gemini_vertex_provider.py
"""

from __future__ import annotations

import asyncio
import sys

from crawler.llm import vertex_config_from_env

from ai_web_research.core.types import ActionKind, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.providers.model_native.gemini_google_vertex import (
    GEMINI_VERTEX_BINDING_ID,
    GEMINI_VERTEX_PROVIDER_ID,
    GEMINI_VERTEX_PROVIDER_VERSION,
    GEMINI_VERTEX_SURFACE_ID,
    GeminiVertexSearchAdapter,
)


def main() -> int:
    if vertex_config_from_env() is None:
        print("SKIPPED_NO_CREDENTIAL")
        return 0
    return asyncio.run(_run_live())


async def _run_live() -> int:
    raw = SearchAction(
        action_id="smoke:gemini-vertex", task_id="smoke", epoch_id="smoke",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef(GEMINI_VERTEX_PROVIDER_ID, GEMINI_VERTEX_PROVIDER_VERSION),
        surface_id=GEMINI_VERTEX_SURFACE_ID, binding_id=GEMINI_VERTEX_BINDING_ID, action_kind=ActionKind.SEARCH,
        inputs=(), parameters={"query": "OpenAI"}, guards=(), expected_effects=(),
        created_by="verify_gemini_vertex_provider", created_at="2026-09-02T00:00:00Z",
    )
    authorized = AuthorizedAction(raw, AuthorizationResult(PolicyDecision.ALLOW))
    context = ExecutionContext("smoke", "smoke", "smoke", services={})
    observation = await GeminiVertexSearchAdapter().execute(authorized, context)
    if not observation.artifacts:
        print("LIVE_FAIL_NO_CANDIDATES")
        return 1
    first_url = observation.artifacts[0].metadata.get("url")
    if not isinstance(first_url, str) or not first_url.startswith(("http://", "https://")):
        print("LIVE_FAIL_INVALID_CANDIDATE")
        return 1
    print(f"LIVE_OK candidates={len(observation.artifacts)} model={observation.metadata['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
