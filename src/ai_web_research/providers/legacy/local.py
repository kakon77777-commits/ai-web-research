from __future__ import annotations

from typing import Awaitable, Callable

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation

from .common import jsonable, occurred_at, require_service, validate_action


SearchFn = Callable[..., Awaitable[object]]


class _LocalSearchAdapter:
    method_id: str
    binding_id: str
    adapter_id: str
    force_no_divergence: bool

    adapter_version = "legacy-ca57faf6"
    provider_id = "provider.local_corpus"
    surface_id = "surface.local.sqlite"

    def __init__(self, search_fn: SearchFn | None = None) -> None:
        self._search_fn = search_fn

    def _legacy_search(self) -> SearchFn:
        if self._search_fn is not None:
            return self._search_fn
        from crawler.identity_search import identity_search
        return identity_search

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id=self.method_id,
            provider_id=self.provider_id,
            surface_id=self.surface_id,
            binding_id=self.binding_id,
        )
        query = str(raw_action.parameters.get("query", "")).strip()
        store = require_service(context, "page_store")
        kwargs = {
            "use_divergence": False if self.force_no_divergence else bool(raw_action.parameters.get("use_divergence", False)),
            "max_branches": int(raw_action.parameters.get("max_branches", 4)),
            "top_k": int(raw_action.parameters.get("top_k", context.runtime_limits.get("max_results", 10))),
        }
        if "llm_config" in context.services:
            kwargs["llm_config"] = context.services["llm_config"]
        if "http_client" in context.services:
            kwargs["client"] = context.services["http_client"]
        result = await self._legacy_search()(query, store, **kwargs)

        artifacts: list[ArtifactRef] = []
        for obj in getattr(result, "objects", []):
            artifacts.append(
                ArtifactRef(
                    kind=ArtifactKind.CANDIDATE,
                    id=str(obj.document_id),
                    metadata={
                        "url": obj.url,
                        "title": obj.title,
                        "has_exact": bool(obj.has_exact),
                        "max_score": float(obj.max_score),
                        "score_semantics": "legacy_identity_search_max_score",
                        "paths": jsonable(obj.paths),
                    },
                )
            )
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=tuple(artifacts),
            raw_ref=None,
            result_count=len(artifacts),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=occurred_at(context),
            metadata={
                "query": getattr(result, "query", query),
                "branches": jsonable(getattr(result, "branches", [])),
                "per_branch": jsonable(getattr(result, "per_branch", [])),
            },
        )


class LegacyIdentitySearchAdapter(_LocalSearchAdapter):
    method_id = "method.identity_search"
    binding_id = "binding.identity_search.local_corpus.v1"
    adapter_id = "legacy.identity_search"
    force_no_divergence = False


class LegacyLexicalSearchAdapter(_LocalSearchAdapter):
    method_id = "method.lexical_search"
    binding_id = "binding.lexical_search.local_corpus.v1"
    adapter_id = "legacy.lexical_search"
    force_no_divergence = True
