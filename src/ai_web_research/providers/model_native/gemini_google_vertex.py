"""Vertex-AI-flavored sibling of gemini_google.py — same MODEL_NATIVE Google
Search capability, different execution channel. Neo, 2026-09-02: use this one
first ("先用2吧") because Vertex still has free trial credit right now; the
AI-Studio-key version (gemini_google.py) is the intended long-term default
once that credit runs out or a real GEMINI_API_KEY exists ("未來還是要用1").
Deliberately a SEPARATE provider/surface/adapter rather than a branch inside
gemini_google.py's adapter — this is exactly the Provider Replaceability
Principle both providers' own position paper states: (Method, Provider_a) ->
(Method, Provider_b) without redefining the Method. Both bind the same
method.lexical_search@1.0.0; swapping which one is "the" Gemini binding later
is a routing/registration change, not a rewrite of either adapter.

Auth reuses this project's existing Vertex service-account path (the same
one src/crawler/llm.py already uses for its own "vertex" LLM provider) rather
than reimplementing OAuth2 by hand — vertex_config_from_env()/
_build_vertex_client() are imported lazily from crawler.llm, mirroring the
providers/legacy/ adapters' own lazy-import-from-crawler pattern.
"""

from __future__ import annotations

from hashlib import sha256
from json import dumps

from ai_web_research.core.types import VersionRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.policy.models import AcquisitionAction, PolicyRule, PolicyRuleEffect, PolicySourceRef, SourcePolicyProfile
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, ProviderTopology, SurfaceKind

from .common import url_candidate_artifacts

GEMINI_VERTEX_PROVIDER_ID = "provider.gemini_google_vertex"
GEMINI_VERTEX_PROVIDER_VERSION = "1.0.0"
GEMINI_VERTEX_SURFACE_ID = "surface.gemini.google_search_vertex"
GEMINI_VERTEX_ADAPTER_ID = "gemini_vertex.google_search"
GEMINI_VERTEX_ADAPTER_VERSION = "1.0.0"
GEMINI_VERTEX_BINDING_ID = "binding.lexical_search.gemini_google_vertex.v1"


class GeminiVertexSearchAdapterError(RuntimeError):
    pass


class GeminiVertexSearchCredentialError(GeminiVertexSearchAdapterError):
    pass


def _policy_hash(rules: tuple[PolicyRule, ...]) -> str:
    payload = [
        {"id": r.rule_id, "action": r.action.value, "effect": r.effect.value, "value": r.value, "constraints": r.constraints}
        for r in rules
    ]
    return sha256(dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def gemini_google_vertex_policy_profile() -> SourcePolicyProfile:
    search_docs = PolicySourceRef(
        source_id="policy-source.gemini-vertex.google-search",
        uri="https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search",
        title="Vertex AI - Grounding with Google Search",
        retrieved_at="2026-09-02T09:00:00+00:00", effective_at=None, expires_at=None,
        content_hash=None, anchor={"section": "Grounding with Google Search"}, authority="provider",
        interpretation_status="provider_human_readable",
    )
    auth_docs = PolicySourceRef(
        source_id="policy-source.gemini-vertex.service-account",
        uri="https://cloud.google.com/vertex-ai/docs/authentication",
        title="Vertex AI service account authentication",
        retrieved_at="2026-09-02T09:00:00+00:00", effective_at=None, expires_at=None,
        content_hash=None, anchor={"section": "Service accounts"}, authority="provider",
        interpretation_status="provider_human_readable",
    )
    rules = (
        PolicyRule(
            rule_id="gemini-vertex-google-search-allow-automated-query", action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.PERMISSION, value=True, asset_scope="google_search_grounding_candidate_urls",
            party_scope=None, purpose_scope=(), constraints={}, source_refs=(search_docs.source_id, auth_docs.source_id),
            priority_hint=10,
        ),
    )
    return SourcePolicyProfile(
        policy_id="policy.gemini_vertex.google_search", version="1.0.0", provider_id=GEMINI_VERTEX_PROVIDER_ID,
        surface_id=GEMINI_VERTEX_SURFACE_ID, asset_scope="google_search_grounding_candidate_urls", rules=rules,
        policy_sources=(search_docs, auth_docs),
        auth_requirements={"scheme": "oauth2_service_account", "credential_required": True, "service_key": "vertex_credentials_path"},
        rate_limits={"provider_managed": True, "project_and_quota_dependent": True}, retention_rules={},
        attribution_rules={"grounding_chunks_returned_by_provider": True},
        redistribution_rules={"third_party_source_content": "not_asserted_by_builtin_profile"},
        privacy_flags=(), observed_at="2026-09-02T09:00:00+00:00", effective_at=None, expires_at=None,
        next_review_at="2026-10-02T00:00:00+00:00", policy_hash=_policy_hash(rules),
        review_status="provider_documented",
        metadata={
            "model_native": True, "tool_type": "google_search", "third_party_source_rights": "not_asserted",
            "evidence_role": "discovery_only", "interim_channel": True,
            "interim_note": "Neo 2026-09-02: temporary while Vertex trial credit lasts; gemini_google.py (AI-Studio key) is the intended long-term default",
        },
    )


def register_gemini_google_vertex_policy(registry) -> None:
    registry.register(gemini_google_vertex_policy_profile())


def register_gemini_google_vertex_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    provider = ProviderSpec(
        provider_id=GEMINI_VERTEX_PROVIDER_ID, version=GEMINI_VERTEX_PROVIDER_VERSION, kind=ProviderKind.SEARCH_ENGINE,
        display_name="Gemini + Google Search grounding (Vertex AI)", domains=("web",), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id=GEMINI_VERTEX_SURFACE_ID, kind=SurfaceKind.AUTHENTICATED_API, endpoint_ref="vertex://generateContent",
            capabilities=frozenset({"capability.lexical", "capability.model_native_search", "capability.url_citations", "capability.search_trace"}),
            auth_profile="vertex_service_account", policy_profile_refs=("policy.gemini_vertex.google_search@1.0.0",),
            static_limits={}, metadata={"tool_type": "google_search", "query_control": "model_delegated", "api": "vertex_generate_content", "interim_channel": True},
        ),), metadata={"official_docs": "https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search", "provider_family": "Google", "interim_channel": True},
        topology=ProviderTopology.MODEL_NATIVE,
    )
    registry.register_provider(provider)
    registry.register_binding(MethodBinding(
        binding_id=GEMINI_VERTEX_BINDING_ID, method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef(GEMINI_VERTEX_PROVIDER_ID, GEMINI_VERTEX_PROVIDER_VERSION), surface_id=GEMINI_VERTEX_SURFACE_ID,
        adapter_id=GEMINI_VERTEX_ADAPTER_ID, adapter_version=GEMINI_VERTEX_ADAPTER_VERSION, enabled=True,
        parameter_mapping={}, metadata={"tool_type": "google_search", "query_control": "model_delegated", "api": "vertex_generate_content"},
    ), methods)


def register_gemini_google_vertex_adapter(registry) -> None:
    registry.register(GeminiVertexSearchAdapter())


def _rows_and_queries(response) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    queries: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        grounding = getattr(candidate, "grounding_metadata", None)
        if grounding is None:
            continue
        for q in (getattr(grounding, "web_search_queries", None) or []):
            if isinstance(q, str) and q not in queries:
                queries.append(q)
        for chunk in (getattr(grounding, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            uri = getattr(web, "uri", None)
            if isinstance(uri, str) and uri.strip():
                rows.append({"url": uri.strip(), "title": getattr(web, "title", None)})
    return rows, queries


class GeminiVertexSearchAdapter:
    adapter_id = GEMINI_VERTEX_ADAPTER_ID
    adapter_version = GEMINI_VERTEX_ADAPTER_VERSION

    def _client_and_model(self, context: ExecutionContext):
        client = context.services.get("gemini_vertex_client")
        model = context.services.get("gemini_vertex_model")
        if client is not None:
            return client, (model if isinstance(model, str) and model.strip() else "gemini-2.5-flash-lite")
        from crawler.llm import _build_vertex_client, vertex_config_from_env

        config = context.services.get("vertex_llm_config") or vertex_config_from_env()
        if config is None or config.provider != "vertex":
            raise GeminiVertexSearchCredentialError(
                "no Vertex config available: set VERTEX_PROJECT_ID + VERTEX_CREDENTIALS_PATH in .env"
            )
        return _build_vertex_client(config), (model if isinstance(model, str) and model.strip() else config.model)

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw = action.action
        if raw.method_ref != VersionRef("method.lexical_search", "1.0.0"):
            raise GeminiVertexSearchAdapterError(f"unsupported method: {raw.method_ref}")
        if raw.provider_ref != VersionRef(GEMINI_VERTEX_PROVIDER_ID, GEMINI_VERTEX_PROVIDER_VERSION):
            raise GeminiVertexSearchAdapterError(f"wrong provider: {raw.provider_ref}")
        if raw.surface_id != GEMINI_VERTEX_SURFACE_ID or raw.binding_id != GEMINI_VERTEX_BINDING_ID:
            raise GeminiVertexSearchAdapterError("action does not match Gemini Vertex Google Search binding")

        query = raw.parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise GeminiVertexSearchAdapterError("Gemini Vertex Google Search requires non-empty query")

        client, model = self._client_and_model(context)

        try:
            from google.genai import types
        except ImportError as exc:
            raise GeminiVertexSearchAdapterError(
                "vertex provider requires the optional 'google-genai' dependency: pip install -e '.[vertex]'"
            ) from exc

        tool = types.Tool(google_search=types.GoogleSearch())
        gen_config = types.GenerateContentConfig(tools=[tool], temperature=0.0, max_output_tokens=1024)
        try:
            response = await client.aio.models.generate_content(model=model, contents=query.strip(), config=gen_config)
        except Exception as exc:
            raise GeminiVertexSearchAdapterError(f"Gemini Vertex Google Search request failed: {exc}") from exc

        rows, executed_queries = _rows_and_queries(response)
        artifacts = url_candidate_artifacts(rows, id_prefix="gemini_vertex", source_type="gemini_vertex_google_search_citation")
        # Live-verified 2026-09-02: Vertex's grounding_chunks.web.uri is a
        # vertexaisearch.cloud.google.com/grounding-api-redirect/... wrapper,
        # not the real source URL — a documented Google product choice
        # (googleapis/python-genai#1512), NOT a parsing bug here. Flagged so
        # downstream code doesn't assume this URL is directly re-fetchable
        # the way Brave/Grok/gemini_google.py's direct URLs are.
        for artifact in artifacts:
            artifact.metadata["url_is_redirect"] = True
        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:gemini_vertex_google", action_id=raw.action_id,
            provider_id=GEMINI_VERTEX_PROVIDER_ID, surface_id=GEMINI_VERTEX_SURFACE_ID, status=ObservationStatus.SUCCEEDED,
            artifacts=artifacts, raw_ref=None, result_count=len(artifacts), cost={}, latency_ms=None,
            continuation={}, diagnostics=(), occurred_at=str(context.services.get("clock") or raw.created_at),
            metadata={
                "query": query.strip(), "model": model, "tool_type": "google_search",
                "provider_execution_mode": "model_native_vertex_generate_content", "query_control": "model_delegated",
                "executed_queries": executed_queries, "citation_count": len(artifacts),
                "evidence_role": "discovery_only", "reasoning_omitted": True, "synthesis_omitted": True,
                "interim_channel": True,
            },
        )
