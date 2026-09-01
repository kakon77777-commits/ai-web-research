from __future__ import annotations

from typing import Awaitable, Callable, Mapping

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation

from .common import LegacyAdapterError, jsonable, occurred_at, require_service, validate_action


ExtractFn = Callable[..., Awaitable[object]]


class LegacySemanticExtractionAdapter:
    adapter_id = "legacy.semantic_extract"
    adapter_version = "legacy-ca57faf6"

    def __init__(self, extract_fn: ExtractFn | None = None) -> None:
        self._extract_fn = extract_fn

    def _legacy_fn(self) -> ExtractFn:
        if self._extract_fn is not None:
            return self._extract_fn
        from crawler.semantic_extract import extract_page
        return extract_page

    def _llm_config(self, context: ExecutionContext):
        if "llm_config" in context.services:
            return context.services["llm_config"]
        from crawler.llm import default_config_from_env
        return default_config_from_env()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id="method.extract_candidate_evidence",
            provider_id="provider.llm_recall",
            surface_id="surface.llm.vertex",
            binding_id="binding.extract_candidate_evidence.llm.v1",
        )
        if len(raw_action.inputs) != 1 or raw_action.inputs[0].kind is not ArtifactKind.DOCUMENT:
            raise LegacyAdapterError("semantic extraction requires exactly one DOCUMENT input")
        schema = raw_action.parameters.get("schema")
        if not isinstance(schema, dict):
            raise LegacyAdapterError("semantic extraction requires a JSON-schema object")
        loader = require_service(context, "document_loader")
        if not callable(loader):
            raise LegacyAdapterError("document_loader service must be callable")
        loaded = loader(raw_action.inputs[0])
        if isinstance(loaded, str):
            markdown = loaded
            url = str(raw_action.inputs[0].metadata.get("url", ""))
            raw_ref = None
        elif isinstance(loaded, Mapping):
            markdown = str(loaded.get("markdown", ""))
            url = str(loaded.get("url") or raw_action.inputs[0].metadata.get("url", ""))
            raw_ref = loaded.get("raw_ref")
        else:
            raise LegacyAdapterError("document_loader must return Markdown text or a mapping")
        if not markdown:
            raise LegacyAdapterError("document_loader returned empty Markdown")
        kwargs = {"url": url}
        if "http_client" in context.services:
            kwargs["client"] = context.services["http_client"]
        result = await self._legacy_fn()(markdown, schema, self._llm_config(context), **kwargs)
        fields = {name: jsonable(field) for name, field in result.fields.items()}
        artifact = ArtifactRef(
            ArtifactKind.EVIDENCE_CANDIDATE,
            f"{raw_action.action_id}:evidence-candidate:1",
            metadata={
                "document_id": raw_action.inputs[0].id,
                "url": result.url,
                "extractor_version": result.extractor_version,
                "provider": result.provider,
                "model": result.model,
                "fields": fields,
                "validation_errors": list(result.validation_errors),
                "source_type": "web_crawled_extraction",
                "verification_scope": "anchor_only",
                "semantic_support_verified": False,
            },
        )
        diagnostics = tuple(str(error) for error in result.validation_errors)
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.PARTIAL if diagnostics else ObservationStatus.SUCCEEDED,
            artifacts=(artifact,),
            raw_ref=str(raw_ref) if raw_ref is not None else None,
            result_count=1,
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=diagnostics,
            occurred_at=occurred_at(context),
            metadata={"verification_scope": "anchor_only"},
        )
