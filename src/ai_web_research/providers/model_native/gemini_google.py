from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Mapping

from ai_web_research.core.types import VersionRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.policy.models import AcquisitionAction, PolicyRule, PolicyRuleEffect, PolicySourceRef, SourcePolicyProfile
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, ProviderTopology, SurfaceKind

from .common import url_candidate_artifacts

GEMINI_PROVIDER_ID = "provider.gemini_google"
GEMINI_PROVIDER_VERSION = "1.0.0"
GEMINI_SURFACE_ID = "surface.gemini.google_search"
GEMINI_ADAPTER_ID = "gemini.google_search"
GEMINI_ADAPTER_VERSION = "1.0.0"
GEMINI_BINDING_ID = "binding.lexical_search.gemini_google.v1"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_DEFAULT_MODEL = "gemini-3.7-flash"


class GeminiGoogleSearchAdapterError(RuntimeError):
    pass


class GeminiGoogleSearchCredentialError(GeminiGoogleSearchAdapterError):
    pass


def _policy_hash(rules: tuple[PolicyRule, ...]) -> str:
    payload = [
        {
            "id": rule.rule_id,
            "action": rule.action.value,
            "effect": rule.effect.value,
            "value": rule.value,
            "constraints": rule.constraints,
        }
        for rule in rules
    ]
    return sha256(dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def gemini_google_policy_profile() -> SourcePolicyProfile:
    search_docs = PolicySourceRef(
        source_id="policy-source.gemini.google-search",
        uri="https://ai.google.dev/gemini-api/docs/google-search",
        title="Gemini API - Grounding with Google Search",
        retrieved_at="2026-09-02T08:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash=None,
        anchor={"section": "Grounding with Google Search"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    auth_docs = PolicySourceRef(
        source_id="policy-source.gemini.api-key",
        uri="https://ai.google.dev/gemini-api/docs/api-key",
        title="Gemini API keys",
        retrieved_at="2026-09-02T08:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash=None,
        anchor={"section": "Using Gemini API keys"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    rules = (
        PolicyRule(
            rule_id="gemini-google-search-allow-automated-query",
            action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.PERMISSION,
            value=True,
            asset_scope="google_search_grounding_candidate_urls",
            party_scope=None,
            purpose_scope=(),
            constraints={},
            source_refs=(search_docs.source_id, auth_docs.source_id),
            priority_hint=10,
        ),
    )
    return SourcePolicyProfile(
        policy_id="policy.gemini.google_search",
        version="1.0.0",
        provider_id=GEMINI_PROVIDER_ID,
        surface_id=GEMINI_SURFACE_ID,
        asset_scope="google_search_grounding_candidate_urls",
        rules=rules,
        policy_sources=(search_docs, auth_docs),
        auth_requirements={"header": "x-goog-api-key", "credential_required": True, "service_key": "gemini_api_key"},
        rate_limits={"provider_managed": True, "account_and_model_dependent": True},
        retention_rules={},
        attribution_rules={"url_citation_annotations": True, "search_suggestions_may_have_display_requirements": True},
        redistribution_rules={"third_party_source_content": "not_asserted_by_builtin_profile"},
        privacy_flags=(),
        observed_at="2026-09-02T08:00:00+00:00",
        effective_at=None,
        expires_at=None,
        next_review_at="2026-10-02T00:00:00+00:00",
        policy_hash=_policy_hash(rules),
        review_status="provider_documented",
        metadata={
            "model_native": True,
            "tool_type": "google_search",
            "third_party_source_rights": "not_asserted",
            "evidence_role": "discovery_only",
            "grounding_availability": "account_and_model_dependent",
        },
    )


def register_gemini_google_policy(registry) -> None:
    registry.register(gemini_google_policy_profile())


def register_gemini_google_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    provider = ProviderSpec(
        provider_id=GEMINI_PROVIDER_ID,
        version=GEMINI_PROVIDER_VERSION,
        kind=ProviderKind.SEARCH_ENGINE,
        display_name="Gemini + Google Search grounding",
        domains=("web",),
        languages=(),
        jurisdictions=(),
        surfaces=(
            ProviderSurface(
                surface_id=GEMINI_SURFACE_ID,
                kind=SurfaceKind.AUTHENTICATED_API,
                endpoint_ref=GEMINI_INTERACTIONS_URL,
                capabilities=frozenset({"capability.lexical", "capability.model_native_search", "capability.url_citations", "capability.search_trace"}),
                auth_profile="gemini_api_key",
                policy_profile_refs=("policy.gemini.google_search@1.0.0",),
                static_limits={},
                metadata={
                    "tool_type": "google_search",
                    "query_control": "model_delegated",
                    "default_model": GEMINI_DEFAULT_MODEL,
                    "api": "interactions",
                },
            ),
        ),
        metadata={"official_docs": "https://ai.google.dev/gemini-api/docs/google-search", "provider_family": "Google"},
        topology=ProviderTopology.MODEL_NATIVE,
    )
    registry.register_provider(provider)
    registry.register_binding(
        MethodBinding(
            binding_id=GEMINI_BINDING_ID,
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(GEMINI_PROVIDER_ID, GEMINI_PROVIDER_VERSION),
            surface_id=GEMINI_SURFACE_ID,
            adapter_id=GEMINI_ADAPTER_ID,
            adapter_version=GEMINI_ADAPTER_VERSION,
            enabled=True,
            parameter_mapping={},
            metadata={"tool_type": "google_search", "query_control": "model_delegated", "api": "interactions"},
        ),
        methods,
    )


def register_gemini_google_adapter(registry) -> None:
    registry.register(GeminiGoogleSearchAdapter())


def _rows_and_queries(payload: Mapping[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    queries: list[str] = []
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return rows, queries
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        step_type = step.get("type")
        if step_type == "google_search_call":
            arguments = step.get("arguments")
            if isinstance(arguments, Mapping):
                raw_queries = arguments.get("queries")
                if isinstance(raw_queries, list):
                    for query in raw_queries:
                        if isinstance(query, str) and query not in queries:
                            queries.append(query)
                single = arguments.get("query")
                if isinstance(single, str) and single not in queries:
                    queries.append(single)
        elif step_type == "google_search_result":
            result = step.get("result")
            items = result if isinstance(result, list) else []
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    rows.append({"url": url.strip(), "title": item.get("title"), "snippet": item.get("snippet")})
        elif step_type == "model_output":
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, Mapping) or block.get("type") != "text":
                    continue
                annotations = block.get("annotations")
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    if not isinstance(annotation, Mapping) or annotation.get("type") != "url_citation":
                        continue
                    url = annotation.get("url")
                    if isinstance(url, str) and url.strip():
                        rows.append({"url": url.strip(), "title": annotation.get("title")})
    return rows, queries


class GeminiGoogleSearchAdapter:
    adapter_id = GEMINI_ADAPTER_ID
    adapter_version = GEMINI_ADAPTER_VERSION

    async def _post(self, context: ExecutionContext, token: str, body: dict[str, object]):
        client = context.services.get("gemini_http_client")
        close_client = False
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=60.0)
            close_client = True
        try:
            return await client.post(
                GEMINI_INTERACTIONS_URL,
                json=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": token},
            )
        finally:
            if close_client:
                await client.aclose()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw = action.action
        if raw.method_ref != VersionRef("method.lexical_search", "1.0.0"):
            raise GeminiGoogleSearchAdapterError(f"unsupported method: {raw.method_ref}")
        if raw.provider_ref != VersionRef(GEMINI_PROVIDER_ID, GEMINI_PROVIDER_VERSION):
            raise GeminiGoogleSearchAdapterError(f"wrong provider: {raw.provider_ref}")
        if raw.surface_id != GEMINI_SURFACE_ID or raw.binding_id != GEMINI_BINDING_ID:
            raise GeminiGoogleSearchAdapterError("action does not match Gemini Google Search binding")

        token = context.services.get("gemini_api_key")
        if not isinstance(token, str) or not token.strip():
            raise GeminiGoogleSearchCredentialError("gemini_api_key is required")
        query = raw.parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise GeminiGoogleSearchAdapterError("Gemini Google Search requires non-empty query")
        model = context.services.get("gemini_google_model", GEMINI_DEFAULT_MODEL)
        if not isinstance(model, str) or not model.strip():
            raise GeminiGoogleSearchAdapterError("gemini_google_model must be a non-empty string")

        body: dict[str, object] = {
            "model": model.strip(),
            "input": query.strip(),
            "tools": [{"type": "google_search"}],
        }
        response = await self._post(context, token.strip(), body)
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise GeminiGoogleSearchAdapterError(f"Gemini Google Search request failed: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise GeminiGoogleSearchAdapterError("Gemini interaction response is not an object")
        status = payload.get("status")
        if status in {"failed", "cancelled"}:
            raise GeminiGoogleSearchAdapterError(f"Gemini interaction ended with status {status}")

        rows, executed_queries = _rows_and_queries(payload)
        artifacts = url_candidate_artifacts(rows, id_prefix="gemini", source_type="gemini_google_search_citation")
        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:gemini_google",
            action_id=raw.action_id,
            provider_id=GEMINI_PROVIDER_ID,
            surface_id=GEMINI_SURFACE_ID,
            status=ObservationStatus.SUCCEEDED,
            artifacts=artifacts,
            raw_ref=None,
            result_count=len(artifacts),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=str(context.services.get("clock") or raw.created_at),
            metadata={
                "query": query.strip(),
                "model": str(payload.get("model") or model.strip()),
                "response_id": str(payload.get("id")) if payload.get("id") is not None else None,
                "interaction_status": str(status) if status is not None else None,
                "tool_type": "google_search",
                "provider_execution_mode": "model_native_server_side_tool",
                "query_control": "model_delegated",
                "executed_queries": executed_queries,
                "citation_count": len(artifacts),
                "evidence_role": "discovery_only",
                "reasoning_omitted": True,
                "synthesis_omitted": True,
            },
        )
