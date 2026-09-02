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

GROK_PROVIDER_ID = "provider.grok"
GROK_PROVIDER_VERSION = "1.0.0"
GROK_WEB_SURFACE_ID = "surface.grok.web_search"
GROK_X_SURFACE_ID = "surface.grok.x_search"
GROK_ADAPTER_ID = "grok.search"
GROK_ADAPTER_VERSION = "1.0.0"
GROK_WEB_BINDING_ID = "binding.lexical_search.grok_web.v1"
GROK_X_BINDING_ID = "binding.lexical_search.grok_x.v1"
GROK_RESPONSES_URL = "https://api.x.ai/v1/responses"
GROK_DEFAULT_MODEL = "grok-4.6"


class GrokSearchAdapterError(RuntimeError):
    pass


class GrokSearchCredentialError(GrokSearchAdapterError):
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


def _policy(surface_id: str, tool_type: str, docs_url: str) -> SourcePolicyProfile:
    docs = PolicySourceRef(
        source_id=f"policy-source.grok.{tool_type}.docs",
        uri=docs_url,
        title=f"xAI {tool_type} documentation",
        retrieved_at="2026-09-02T08:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash=None,
        anchor={"section": "Responses API built-in search tool"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    terms = PolicySourceRef(
        source_id="policy-source.grok.enterprise-terms",
        uri="https://x.ai/legal/terms-of-service-enterprise",
        title="SpaceXAI Terms of Service - Enterprise",
        retrieved_at="2026-09-02T08:00:00+00:00",
        effective_at="2026-08-14T00:00:00+00:00",
        expires_at=None,
        content_hash=None,
        anchor={"section": "1.1 Access to and Use of Services"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    rules = (
        PolicyRule(
            rule_id=f"grok-{tool_type}-allow-automated-query",
            action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.PERMISSION,
            value=True,
            asset_scope="model_native_search_candidate_urls",
            party_scope=None,
            purpose_scope=(),
            constraints={},
            source_refs=(docs.source_id, terms.source_id),
            priority_hint=10,
        ),
    )
    return SourcePolicyProfile(
        policy_id=f"policy.grok.{tool_type}",
        version="1.0.0",
        provider_id=GROK_PROVIDER_ID,
        surface_id=surface_id,
        asset_scope="model_native_search_candidate_urls",
        rules=rules,
        policy_sources=(docs, terms),
        auth_requirements={"scheme": "Bearer", "credential_required": True, "service_key": "xai_api_key"},
        rate_limits={"provider_managed": True, "account_dependent": True},
        retention_rules={},
        attribution_rules={"citations_returned_by_provider": True},
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
            "tool_type": tool_type,
            "third_party_source_rights": "not_asserted",
            "evidence_role": "discovery_only",
        },
    )


def grok_policy_profiles() -> tuple[SourcePolicyProfile, ...]:
    return (
        _policy(GROK_WEB_SURFACE_ID, "web_search", "https://docs.x.ai/developers/tools/web-search"),
        _policy(GROK_X_SURFACE_ID, "x_search", "https://docs.x.ai/developers/tools/x-search"),
    )


def register_grok_policies(registry) -> None:
    for profile in grok_policy_profiles():
        registry.register(profile)


def register_grok_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    provider = ProviderSpec(
        provider_id=GROK_PROVIDER_ID,
        version=GROK_PROVIDER_VERSION,
        kind=ProviderKind.SEARCH_ENGINE,
        display_name="Grok model-native search",
        domains=("web", "social"),
        languages=(),
        jurisdictions=(),
        surfaces=(
            ProviderSurface(
                surface_id=GROK_WEB_SURFACE_ID,
                kind=SurfaceKind.AUTHENTICATED_API,
                endpoint_ref=GROK_RESPONSES_URL,
                capabilities=frozenset({"capability.lexical", "capability.model_native_search", "capability.url_citations", "capability.domain_filter"}),
                auth_profile="xai_api_key",
                policy_profile_refs=("policy.grok.web_search@1.0.0",),
                static_limits={"allowed_domains_max": 5, "excluded_domains_max": 5},
                metadata={"tool_type": "web_search", "query_control": "model_delegated", "default_model": GROK_DEFAULT_MODEL},
            ),
            ProviderSurface(
                surface_id=GROK_X_SURFACE_ID,
                kind=SurfaceKind.AUTHENTICATED_API,
                endpoint_ref=GROK_RESPONSES_URL,
                capabilities=frozenset({"capability.lexical", "capability.model_native_search", "capability.url_citations", "capability.social_search", "capability.date_filter"}),
                auth_profile="xai_api_key",
                policy_profile_refs=("policy.grok.x_search@1.0.0",),
                static_limits={"allowed_x_handles_max": 20, "excluded_x_handles_max": 20},
                metadata={"tool_type": "x_search", "query_control": "model_delegated", "default_model": GROK_DEFAULT_MODEL},
            ),
        ),
        metadata={"official_docs": "https://docs.x.ai/developers/tools/overview", "provider_family": "xAI"},
        topology=ProviderTopology.MODEL_NATIVE,
    )
    registry.register_provider(provider)
    for binding in (
        MethodBinding(
            binding_id=GROK_WEB_BINDING_ID,
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(GROK_PROVIDER_ID, GROK_PROVIDER_VERSION),
            surface_id=GROK_WEB_SURFACE_ID,
            adapter_id=GROK_ADAPTER_ID,
            adapter_version=GROK_ADAPTER_VERSION,
            enabled=True,
            parameter_mapping={},
            metadata={"tool_type": "web_search", "query_control": "model_delegated"},
        ),
        MethodBinding(
            binding_id=GROK_X_BINDING_ID,
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(GROK_PROVIDER_ID, GROK_PROVIDER_VERSION),
            surface_id=GROK_X_SURFACE_ID,
            adapter_id=GROK_ADAPTER_ID,
            adapter_version=GROK_ADAPTER_VERSION,
            enabled=True,
            parameter_mapping={},
            metadata={"tool_type": "x_search", "query_control": "model_delegated"},
        ),
    ):
        registry.register_binding(binding, methods)


def register_grok_adapter(registry) -> None:
    registry.register(GrokSearchAdapter())


def _string_list(value: object, *, name: str, max_items: int) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise GrokSearchAdapterError(f"{name} must be a list of non-empty strings")
    if len(value) > max_items:
        raise GrokSearchAdapterError(f"{name} supports at most {max_items} entries")
    return [item.strip() for item in value]


def _citation_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    titled: dict[str, str | None] = {}
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, Mapping) or block.get("type") != "output_text":
                    continue
                annotations = block.get("annotations")
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    if not isinstance(annotation, Mapping):
                        continue
                    url = annotation.get("url")
                    if isinstance(url, str) and url.strip():
                        title = annotation.get("title")
                        titled[url.strip()] = str(title) if title is not None else None
    for url, title in titled.items():
        rows.append({"url": url, "title": title})
    citations = payload.get("citations")
    if isinstance(citations, list):
        for citation in citations:
            if isinstance(citation, str) and citation.strip():
                rows.append({"url": citation.strip(), "title": titled.get(citation.strip())})
    return rows


class GrokSearchAdapter:
    adapter_id = GROK_ADAPTER_ID
    adapter_version = GROK_ADAPTER_VERSION

    async def _post(self, context: ExecutionContext, token: str, body: dict[str, object]):
        client = context.services.get("grok_http_client")
        close_client = False
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=60.0)
            close_client = True
        try:
            return await client.post(
                GROK_RESPONSES_URL,
                json=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            )
        finally:
            if close_client:
                await client.aclose()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw = action.action
        if raw.method_ref != VersionRef("method.lexical_search", "1.0.0"):
            raise GrokSearchAdapterError(f"unsupported method: {raw.method_ref}")
        if raw.provider_ref != VersionRef(GROK_PROVIDER_ID, GROK_PROVIDER_VERSION):
            raise GrokSearchAdapterError(f"wrong provider: {raw.provider_ref}")
        if raw.surface_id == GROK_WEB_SURFACE_ID and raw.binding_id == GROK_WEB_BINDING_ID:
            tool_type = "web_search"
        elif raw.surface_id == GROK_X_SURFACE_ID and raw.binding_id == GROK_X_BINDING_ID:
            tool_type = "x_search"
        else:
            raise GrokSearchAdapterError("action does not match a Grok search binding")

        token = context.services.get("xai_api_key")
        if not isinstance(token, str) or not token.strip():
            raise GrokSearchCredentialError("xai_api_key is required")
        query = raw.parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise GrokSearchAdapterError("Grok search requires non-empty query")
        model = context.services.get("grok_model", GROK_DEFAULT_MODEL)
        if not isinstance(model, str) or not model.strip():
            raise GrokSearchAdapterError("grok_model must be a non-empty string")

        tool: dict[str, object] = {"type": tool_type}
        if tool_type == "web_search":
            allowed = _string_list(raw.parameters.get("allowed_domains"), name="allowed_domains", max_items=5)
            excluded = _string_list(raw.parameters.get("excluded_domains"), name="excluded_domains", max_items=5)
            if allowed and excluded:
                raise GrokSearchAdapterError("allowed_domains and excluded_domains cannot be combined")
            if allowed:
                tool["filters"] = {"allowed_domains": allowed}
            elif excluded:
                tool["filters"] = {"excluded_domains": excluded}
            for key in ("enable_image_understanding", "enable_image_search"):
                value = raw.parameters.get(key)
                if isinstance(value, bool):
                    tool[key] = value
        else:
            for key in ("allowed_x_handles", "excluded_x_handles"):
                values = _string_list(raw.parameters.get(key), name=key, max_items=20)
                if values:
                    tool[key] = values
            for key in ("from_date", "to_date"):
                value = raw.parameters.get(key)
                if isinstance(value, str) and value.strip():
                    tool[key] = value.strip()
            for key in ("enable_image_understanding", "enable_video_understanding"):
                value = raw.parameters.get(key)
                if isinstance(value, bool):
                    tool[key] = value

        body: dict[str, object] = {
            "model": model.strip(),
            "input": [{"role": "user", "content": query.strip()}],
            "tools": [tool],
        }
        response = await self._post(context, token.strip(), body)
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise GrokSearchAdapterError(f"Grok search request failed: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise GrokSearchAdapterError("Grok response is not an object")

        source_type = "grok_web_search_citation" if tool_type == "web_search" else "grok_x_search_citation"
        artifacts = url_candidate_artifacts(_citation_rows(payload), id_prefix="grok", source_type=source_type)
        usage = payload.get("usage")
        metadata: dict[str, object] = {
            "query": query.strip(),
            "model": str(payload.get("model") or model.strip()),
            "tool_type": tool_type,
            "response_id": str(payload.get("id")) if payload.get("id") is not None else None,
            "provider_execution_mode": "model_native_server_side_tool",
            "query_control": "model_delegated",
            "citation_count": len(artifacts),
            "evidence_role": "discovery_only",
            "reasoning_omitted": True,
            "synthesis_omitted": True,
        }
        if isinstance(usage, Mapping):
            metadata["usage"] = {str(k): v for k, v in usage.items()}
        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:grok:{tool_type}",
            action_id=raw.action_id,
            provider_id=GROK_PROVIDER_ID,
            surface_id=raw.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=artifacts,
            raw_ref=None,
            result_count=len(artifacts),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=str(context.services.get("clock") or raw.created_at),
            metadata=metadata,
        )
