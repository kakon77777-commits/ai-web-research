import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.model_native.gemini_google import (
    GeminiGoogleSearchAdapter,
    GeminiGoogleSearchCredentialError,
    gemini_google_policy_profile,
    register_gemini_google_adapter,
    register_gemini_google_policy,
    register_gemini_google_provider,
)
from ai_web_research.providers.model_native.grok import (
    GrokSearchAdapter,
    GrokSearchCredentialError,
    grok_policy_profiles,
    register_grok_adapter,
    register_grok_policies,
    register_grok_provider,
)
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import ProviderTopology, SurfaceKind


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


class FakePostClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def post(self, url, *, json=None, headers=None):
        self.calls.append((url, json or {}, headers or {}))
        return self.response


def methods_snapshot():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    return methods.snapshot()


def search_action(*, provider_id, surface_id, binding_id, params=None):
    return SearchAction(
        action_id="search-1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef(provider_id, "1.0.0"),
        surface_id=surface_id,
        binding_id=binding_id,
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters=params or {"query": "latest AI research"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-09-02T08:00:00+00:00",
    )


def allow(action):
    return AuthorizedAction(action, AuthorizationResult(PolicyDecision.ALLOW))


def policy_context():
    return PolicyContext(
        task_id="task-1",
        purpose="research",
        party_profile_id=None,
        risk_class=RiskClass.LOW,
        jurisdiction_context=(),
        requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
        timestamp="2026-09-02T08:00:00+00:00",
    )


def test_grok_is_one_model_native_provider_with_web_and_x_surfaces():
    providers = ProviderRegistry()
    register_grok_provider(providers, methods_snapshot())
    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.grok", "1.0.0"))
    assert provider.topology is ProviderTopology.MODEL_NATIVE
    assert {s.surface_id for s in provider.surfaces} == {
        "surface.grok.web_search",
        "surface.grok.x_search",
    }
    assert all(s.kind is SurfaceKind.AUTHENTICATED_API for s in provider.surfaces)
    assert snapshot.get_binding("binding.lexical_search.grok_web.v1").adapter_id == "grok.search"
    assert snapshot.get_binding("binding.lexical_search.grok_x.v1").adapter_id == "grok.search"
    assert all(b.method_ref.id == "method.lexical_search" for b in snapshot.bindings)


@pytest.mark.asyncio
async def test_grok_web_uses_responses_api_and_normalizes_citations_only():
    response = FakeResponse({
        "id": "resp-1",
        "model": "grok-4.6",
        "citations": ["https://x.ai/news", "https://example.org/report"],
        "output": [
            {
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "synthesized answer that is not evidence",
                    "annotations": [
                        {"type": "url_citation", "url": "https://x.ai/news", "title": "xAI News"}
                    ],
                }],
            },
            {"type": "reasoning", "summary": [{"text": "private provider reasoning"}]},
        ],
        "usage": {"input_tokens": 40, "output_tokens": 20, "total_tokens": 60},
    })
    client = FakePostClient(response)
    action = search_action(
        provider_id="provider.grok",
        surface_id="surface.grok.web_search",
        binding_id="binding.lexical_search.grok_web.v1",
        params={
            "query": "latest AI research",
            "allowed_domains": ["x.ai", "example.org"],
            "enable_image_understanding": True,
        },
    )
    obs = await GrokSearchAdapter().execute(
        allow(action),
        ExecutionContext(
            task_id="task-1",
            epoch_id="epoch-1",
            registry_snapshot_id="snapshot",
            services={"xai_api_key": "secret-xai", "grok_http_client": client},
            runtime_limits={},
        ),
    )
    url, body, headers = client.calls[0]
    assert url == "https://api.x.ai/v1/responses"
    assert headers["Authorization"] == "Bearer secret-xai"
    assert body["model"] == "grok-4.6"
    assert body["input"] == [{"role": "user", "content": "latest AI research"}]
    assert body["tools"] == [{
        "type": "web_search",
        "filters": {"allowed_domains": ["x.ai", "example.org"]},
        "enable_image_understanding": True,
    }]
    assert [a.metadata["url"] for a in obs.artifacts] == ["https://x.ai/news", "https://example.org/report"]
    assert obs.artifacts[0].metadata["title"] == "xAI News"
    assert all(a.kind is ArtifactKind.CANDIDATE for a in obs.artifacts)
    assert all(a.metadata["evidence_role"] == "discovery_only" for a in obs.artifacts)
    assert obs.metadata["model"] == "grok-4.6"
    assert obs.metadata["tool_type"] == "web_search"
    assert obs.metadata["provider_execution_mode"] == "model_native_server_side_tool"
    assert obs.metadata["reasoning_omitted"] is True
    assert "synthesized answer" not in repr(obs)
    assert "private provider reasoning" not in repr(obs)
    assert "secret-xai" not in repr(obs)


@pytest.mark.asyncio
async def test_grok_x_maps_x_search_filters_without_creating_brand_method():
    client = FakePostClient(FakeResponse({
        "id": "resp-x",
        "citations": ["https://x.com/i/status/123"],
        "output": [],
    }))
    action = search_action(
        provider_id="provider.grok",
        surface_id="surface.grok.x_search",
        binding_id="binding.lexical_search.grok_x.v1",
        params={
            "query": "AI policy discussion",
            "allowed_x_handles": ["xai", "OpenAI"],
            "excluded_x_handles": ["spam"],
            "from_date": "2026-08-01",
            "to_date": "2026-09-02",
            "enable_image_understanding": True,
            "enable_video_understanding": True,
        },
    )
    obs = await GrokSearchAdapter().execute(
        allow(action),
        ExecutionContext("task-1", "epoch-1", "snapshot", {"xai_api_key": "k", "grok_http_client": client}, {}),
    )
    tool = client.calls[0][1]["tools"][0]
    assert tool == {
        "type": "x_search",
        "allowed_x_handles": ["xai", "OpenAI"],
        "excluded_x_handles": ["spam"],
        "from_date": "2026-08-01",
        "to_date": "2026-09-02",
        "enable_image_understanding": True,
        "enable_video_understanding": True,
    }
    assert obs.artifacts[0].metadata["source_type"] == "grok_x_search_citation"
    assert obs.metadata["tool_type"] == "x_search"


@pytest.mark.asyncio
async def test_grok_missing_api_key_fails_before_transport():
    client = FakePostClient(FakeResponse({}))
    action = search_action(
        provider_id="provider.grok",
        surface_id="surface.grok.web_search",
        binding_id="binding.lexical_search.grok_web.v1",
    )
    with pytest.raises(GrokSearchCredentialError):
        await GrokSearchAdapter().execute(
            allow(action), ExecutionContext("task-1", "epoch-1", "snapshot", {"grok_http_client": client}, {})
        )
    assert client.calls == []


def test_grok_policies_allow_machine_query_but_do_not_assert_third_party_redistribution():
    providers = ProviderRegistry()
    register_grok_provider(providers, methods_snapshot())
    provider_snapshot = providers.snapshot()
    policies = SourcePolicyRegistry()
    register_grok_policies(policies)
    assert len(grok_policy_profiles()) == 2
    for surface_id in ("surface.grok.web_search", "surface.grok.x_search"):
        provider = provider_snapshot.get_provider(VersionRef("provider.grok", "1.0.0"))
        surface = provider_snapshot.surface(provider.ref if hasattr(provider, "ref") else VersionRef("provider.grok", "1.0.0"), surface_id)
        action = search_action(
            provider_id="provider.grok",
            surface_id=surface_id,
            binding_id=("binding.lexical_search.grok_web.v1" if surface_id.endswith("web_search") else "binding.lexical_search.grok_x.v1"),
        )
        evaluation = DeterministicPolicyEvaluator().evaluate(
            action,
            provider,
            surface,
            policy_context(),
            policies.snapshot().profiles_for("provider.grok", surface_id),
        )
        assert evaluation.authorization.is_executable
        assert AcquisitionAction.AUTOMATED_QUERY in evaluation.usage_seed.permissions
        assert AcquisitionAction.REDISTRIBUTE_RAW not in evaluation.usage_seed.permissions


def test_gemini_google_is_model_native_and_reuses_lexical_search():
    providers = ProviderRegistry()
    register_gemini_google_provider(providers, methods_snapshot())
    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.gemini_google", "1.0.0"))
    assert provider.topology is ProviderTopology.MODEL_NATIVE
    surface = snapshot.surface(VersionRef("provider.gemini_google", "1.0.0"), "surface.gemini.google_search")
    assert surface.kind is SurfaceKind.AUTHENTICATED_API
    binding = snapshot.get_binding("binding.lexical_search.gemini_google.v1")
    assert binding.method_ref == VersionRef("method.lexical_search", "1.0.0")
    assert binding.adapter_id == "gemini.google_search"


@pytest.mark.asyncio
async def test_gemini_interactions_api_normalizes_search_results_and_annotations():
    response = FakeResponse({
        "id": "interaction-1",
        "status": "completed",
        "model": "gemini-3.7-flash",
        "steps": [
            {"type": "thought", "signature": "opaque-signature"},
            {"type": "google_search_call", "arguments": {"queries": ["AI research 2026", "AI benchmarks"]}},
            {"type": "google_search_result", "result": [
                {"title": "Research A", "url": "https://example.org/a", "snippet": "A snippet"},
                {"title": "Research B", "url": "https://example.org/b", "snippet": "B snippet"},
            ]},
            {"type": "model_output", "content": [{
                "type": "text",
                "text": "provider synthesis",
                "annotations": [
                    {"type": "url_citation", "url": "https://example.org/b", "title": "Research B"},
                    {"type": "url_citation", "url": "https://example.org/c", "title": "Research C"},
                ],
            }]},
        ],
    })
    client = FakePostClient(response)
    action = search_action(
        provider_id="provider.gemini_google",
        surface_id="surface.gemini.google_search",
        binding_id="binding.lexical_search.gemini_google.v1",
    )
    obs = await GeminiGoogleSearchAdapter().execute(
        allow(action),
        ExecutionContext(
            "task-1", "epoch-1", "snapshot",
            {"gemini_api_key": "secret-google", "gemini_http_client": client}, {},
        ),
    )
    url, body, headers = client.calls[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert headers["x-goog-api-key"] == "secret-google"
    assert body == {
        "model": "gemini-3.7-flash",
        "input": "latest AI research",
        "tools": [{"type": "google_search"}],
    }
    assert [a.metadata["url"] for a in obs.artifacts] == [
        "https://example.org/a", "https://example.org/b", "https://example.org/c"
    ]
    assert obs.artifacts[0].metadata["snippet"] == "A snippet"
    assert obs.metadata["executed_queries"] == ["AI research 2026", "AI benchmarks"]
    assert obs.metadata["reasoning_omitted"] is True
    assert obs.metadata["model"] == "gemini-3.7-flash"
    assert "provider synthesis" not in repr(obs)
    assert "opaque-signature" not in repr(obs)
    assert "secret-google" not in repr(obs)


@pytest.mark.asyncio
async def test_gemini_missing_api_key_fails_before_transport():
    client = FakePostClient(FakeResponse({}))
    action = search_action(
        provider_id="provider.gemini_google",
        surface_id="surface.gemini.google_search",
        binding_id="binding.lexical_search.gemini_google.v1",
    )
    with pytest.raises(GeminiGoogleSearchCredentialError):
        await GeminiGoogleSearchAdapter().execute(
            allow(action), ExecutionContext("task-1", "epoch-1", "snapshot", {"gemini_http_client": client}, {})
        )
    assert client.calls == []


def test_gemini_policy_allows_automated_google_search_without_asserting_source_rights():
    providers = ProviderRegistry()
    register_gemini_google_provider(providers, methods_snapshot())
    snapshot = providers.snapshot()
    policies = SourcePolicyRegistry()
    register_gemini_google_policy(policies)
    provider = snapshot.get_provider(VersionRef("provider.gemini_google", "1.0.0"))
    surface = snapshot.surface(VersionRef("provider.gemini_google", "1.0.0"), "surface.gemini.google_search")
    action = search_action(
        provider_id="provider.gemini_google",
        surface_id="surface.gemini.google_search",
        binding_id="binding.lexical_search.gemini_google.v1",
    )
    evaluation = DeterministicPolicyEvaluator().evaluate(
        action, provider, surface, policy_context(),
        policies.snapshot().profiles_for("provider.gemini_google", "surface.gemini.google_search"),
    )
    assert evaluation.authorization.is_executable
    assert AcquisitionAction.AUTOMATED_QUERY in evaluation.usage_seed.permissions
    assert AcquisitionAction.REDISTRIBUTE_RAW not in evaluation.usage_seed.permissions
    assert gemini_google_policy_profile().metadata["third_party_source_rights"] == "not_asserted"


def test_adapter_registration_is_exact_versioned_for_both_model_native_providers():
    registry = AdapterRegistry()
    register_grok_adapter(registry)
    register_gemini_google_adapter(registry)
    assert isinstance(registry.get("grok.search", "1.0.0"), GrokSearchAdapter)
    assert isinstance(registry.get("gemini.google_search", "1.0.0"), GeminiGoogleSearchAdapter)
