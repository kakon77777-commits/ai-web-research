from __future__ import annotations

import asyncio
import os


def main() -> int:
    token = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not token:
        print("SKIPPED_NO_CREDENTIAL")
        return 0
    return asyncio.run(_run_live(token))


async def _run_live(token: str) -> int:
    from ai_web_research.core.types import ActionKind, SearchAction, VersionRef
    from ai_web_research.execution.models import AuthorizedAction, AuthorizationResult, ExecutionContext, PolicyDecision
    from ai_web_research.providers.brave_search import (
        BRAVE_BINDING_ID, BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION, BRAVE_SURFACE_ID, BraveSearchAdapter,
    )
    raw = SearchAction(
        action_id="smoke:brave-search", task_id="smoke", epoch_id="smoke",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef(BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION),
        surface_id=BRAVE_SURFACE_ID, binding_id=BRAVE_BINDING_ID, action_kind=ActionKind.SEARCH,
        inputs=(), parameters={"query":"OpenAI","top_k":1}, guards=(), expected_effects=(),
        created_by="verify_brave_search_provider", created_at="2026-08-31T16:00:00Z",
    )
    authorized = AuthorizedAction(raw, AuthorizationResult(PolicyDecision.ALLOW))
    context = ExecutionContext("smoke", "smoke", "smoke", services={"brave_search_api_key":token})
    observation = await BraveSearchAdapter().execute(authorized, context)
    if not observation.artifacts:
        print("LIVE_FAIL_NO_CANDIDATES"); return 1
    first_url = observation.artifacts[0].metadata.get("url")
    if not isinstance(first_url, str) or not first_url.startswith(("http://","https://")):
        print("LIVE_FAIL_INVALID_CANDIDATE"); return 1
    print(f"LIVE_OK candidates={len(observation.artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
