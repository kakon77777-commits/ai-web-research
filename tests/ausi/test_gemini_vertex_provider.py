from types import SimpleNamespace

import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.model_native.gemini_google_vertex import (
    GeminiVertexSearchAdapter,
    GeminiVertexSearchCredentialError,
    gemini_google_vertex_policy_profile,
    register_gemini_google_vertex_adapter,
    register_gemini_google_vertex_policy,
    register_gemini_google_vertex_provider,
)
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import ProviderTopology, SurfaceKind


def methods_snapshot():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    return methods.snapshot()


def search_action(*, params=None):
    return SearchAction(
        action_id="search-1", task_id="task-1", epoch_id="epoch-1",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.gemini_google_vertex", "1.0.0"),
        surface_id="surface.gemini.google_search_vertex", binding_id="binding.lexical_search.gemini_google_vertex.v1",
        action_kind=ActionKind.SEARCH, inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters=params or {"query": "latest AI research"}, guards=(), expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0", created_at="2026-09-02T09:00:00+00:00",
    )


def allow(action):
    return AuthorizedAction(action, AuthorizationResult(PolicyDecision.ALLOW))


def policy_context():
    return PolicyContext(
        task_id="task-1", purpose="research", party_profile_id=None, risk_class=RiskClass.LOW,
        jurisdiction_context=(), requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
        timestamp="2026-09-02T09:00:00+00:00",
    )


def _fake_response(chunks, queries):
    web_chunks = [SimpleNamespace(web=SimpleNamespace(uri=url, title=title, domain=None)) for url, title in chunks]
    grounding = SimpleNamespace(grounding_chunks=web_chunks, web_search_queries=queries)
    candidate = SimpleNamespace(grounding_metadata=grounding)
    return SimpleNamespace(candidates=[candidate])


class FakeAioModels:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self._response


class FakeVertexClient:
    def __init__(self, response):
        self.aio = SimpleNamespace(models=FakeAioModels(response))


def test_gemini_vertex_is_a_distinct_model_native_provider_from_the_ai_studio_one():
    providers = ProviderRegistry()
    register_gemini_google_vertex_provider(providers, methods_snapshot())
    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.gemini_google_vertex", "1.0.0"))
    assert provider.topology is ProviderTopology.MODEL_NATIVE
    assert provider.provider_id != "provider.gemini_google"
    surface = snapshot.surface(VersionRef("provider.gemini_google_vertex", "1.0.0"), "surface.gemini.google_search_vertex")
    assert surface.kind is SurfaceKind.AUTHENTICATED_API
    binding = snapshot.get_binding("binding.lexical_search.gemini_google_vertex.v1")
    assert binding.method_ref == VersionRef("method.lexical_search", "1.0.0")
    assert binding.adapter_id == "gemini_vertex.google_search"


@pytest.mark.asyncio
async def test_gemini_vertex_normalizes_grounding_chunks_and_omits_synthesis():
    response = _fake_response(
        chunks=[("https://example.org/a", "Research A"), ("https://example.org/b", "Research B")],
        queries=["AI research 2026"],
    )
    client = FakeVertexClient(response)
    action = search_action()
    obs = await GeminiVertexSearchAdapter().execute(
        allow(action),
        ExecutionContext("task-1", "epoch-1", "snapshot", {"gemini_vertex_client": client}, {}),
    )
    call = client.aio.models.calls[0]
    assert call["contents"] == "latest AI research"
    assert call["model"] == "gemini-2.5-flash-lite"
    assert [a.metadata["url"] for a in obs.artifacts] == ["https://example.org/a", "https://example.org/b"]
    assert obs.artifacts[0].metadata["title"] == "Research A"
    assert all(a.kind is ArtifactKind.CANDIDATE for a in obs.artifacts)
    assert all(a.metadata["evidence_role"] == "discovery_only" for a in obs.artifacts)
    assert obs.metadata["executed_queries"] == ["AI research 2026"]
    assert obs.metadata["provider_execution_mode"] == "model_native_vertex_generate_content"
    assert obs.metadata["reasoning_omitted"] is True
    assert obs.metadata["synthesis_omitted"] is True
    assert obs.metadata["interim_channel"] is True
    assert all(a.metadata["url_is_redirect"] is True for a in obs.artifacts)


@pytest.mark.asyncio
async def test_gemini_vertex_model_override_via_context_service():
    client = FakeVertexClient(_fake_response(chunks=[], queries=[]))
    obs = await GeminiVertexSearchAdapter().execute(
        allow(search_action()),
        ExecutionContext(
            "task-1", "epoch-1", "snapshot",
            {"gemini_vertex_client": client, "gemini_vertex_model": "gemini-3.7-flash"}, {},
        ),
    )
    assert client.aio.models.calls[0]["model"] == "gemini-3.7-flash"
    assert obs.metadata["model"] == "gemini-3.7-flash"


@pytest.mark.asyncio
async def test_gemini_vertex_missing_config_fails_before_transport(monkeypatch):
    import crawler.llm as llm_module

    monkeypatch.setattr(llm_module, "vertex_config_from_env", lambda: None)
    with pytest.raises(GeminiVertexSearchCredentialError):
        await GeminiVertexSearchAdapter().execute(
            allow(search_action()), ExecutionContext("task-1", "epoch-1", "snapshot", {}, {})
        )


def test_gemini_vertex_policy_allows_automated_query_without_asserting_source_rights():
    providers = ProviderRegistry()
    register_gemini_google_vertex_provider(providers, methods_snapshot())
    snapshot = providers.snapshot()
    policies = SourcePolicyRegistry()
    register_gemini_google_vertex_policy(policies)
    provider = snapshot.get_provider(VersionRef("provider.gemini_google_vertex", "1.0.0"))
    surface = snapshot.surface(VersionRef("provider.gemini_google_vertex", "1.0.0"), "surface.gemini.google_search_vertex")
    evaluation = DeterministicPolicyEvaluator().evaluate(
        search_action(), provider, surface, policy_context(),
        policies.snapshot().profiles_for("provider.gemini_google_vertex", "surface.gemini.google_search_vertex"),
    )
    assert evaluation.authorization.is_executable
    assert AcquisitionAction.AUTOMATED_QUERY in evaluation.usage_seed.permissions
    assert AcquisitionAction.REDISTRIBUTE_RAW not in evaluation.usage_seed.permissions
    assert gemini_google_vertex_policy_profile().metadata["third_party_source_rights"] == "not_asserted"
    assert gemini_google_vertex_policy_profile().metadata["interim_channel"] is True


def test_gemini_vertex_adapter_registration_is_exact_versioned():
    registry = AdapterRegistry()
    register_gemini_google_vertex_adapter(registry)
    assert isinstance(registry.get("gemini_vertex.google_search", "1.0.0"), GeminiVertexSearchAdapter)
