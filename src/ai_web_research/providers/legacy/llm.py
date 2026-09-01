from __future__ import annotations

from typing import Awaitable, Callable

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation

from .common import occurred_at, validate_action


AsyncFn = Callable[..., Awaitable[object]]


class LegacyDivergenceAdapter:
    adapter_id = "legacy.diverge"
    adapter_version = "legacy-ca57faf6"

    def __init__(self, diverge_fn: AsyncFn | None = None) -> None:
        self._diverge_fn = diverge_fn

    def _legacy_fn(self) -> AsyncFn:
        if self._diverge_fn is not None:
            return self._diverge_fn
        from crawler.research import diverge
        return diverge

    def _llm_config(self, context: ExecutionContext):
        if "llm_config" in context.services:
            return context.services["llm_config"]
        from crawler.llm import default_config_from_env
        return default_config_from_env()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id="method.query_divergence",
            provider_id="provider.llm_recall",
            surface_id="surface.llm.vertex",
            binding_id="binding.query_divergence.llm.v1",
        )
        query = str(raw_action.parameters.get("query", "")).strip()
        kwargs = {}
        if "http_client" in context.services:
            kwargs["client"] = context.services["http_client"]
        result = await self._legacy_fn()(query, self._llm_config(context), **kwargs)
        artifact = ArtifactRef(
            ArtifactKind.QUERY_SET,
            f"{raw_action.action_id}:query-set",
            metadata={"seed": result.seed, "branches": result.branches},
        )
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(artifact,),
            raw_ref=None,
            result_count=sum(len(v) for v in result.branches.values()),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=occurred_at(context),
            metadata={"source_type": "llm_query_generation"},
        )


class LegacyLlmRecallAdapter:
    adapter_id = "legacy.basic_ai_search"
    adapter_version = "legacy-ca57faf6"

    def __init__(self, recall_fn: AsyncFn | None = None) -> None:
        self._recall_fn = recall_fn

    def _legacy_fn(self) -> AsyncFn:
        if self._recall_fn is not None:
            return self._recall_fn
        from crawler.research import basic_ai_search
        return basic_ai_search

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id="method.llm_recall",
            provider_id="provider.llm_recall",
            surface_id="surface.llm.vertex",
            binding_id="binding.llm_recall.llm.v1",
        )
        query = str(raw_action.parameters.get("query", "")).strip()
        branch = str(raw_action.parameters.get("branch", "original"))
        queries = raw_action.parameters.get("queries")
        if not isinstance(queries, list) or not queries:
            queries = [query]
        kwargs = {}
        if "llm_config" in context.services:
            kwargs["llm_config"] = context.services["llm_config"]
        if "http_client" in context.services:
            kwargs["client"] = context.services["http_client"]
        result = await self._legacy_fn()(query, branch, [str(q) for q in queries], **kwargs)
        artifact = ArtifactRef(
            ArtifactKind.CANDIDATE,
            f"{raw_action.action_id}:llm-recall:1",
            metadata={
                "branch": result.branch,
                "queries": list(result.queries),
                "answer": result.answer,
                "model": result.model,
                "source_type": "llm_recall",
                "external_evidence": False,
            },
        )
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(artifact,),
            raw_ref=None,
            result_count=1,
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=("model prior only; not live external evidence",),
            occurred_at=occurred_at(context),
            metadata={"source_type": "llm_recall", "external_evidence": False},
        )
