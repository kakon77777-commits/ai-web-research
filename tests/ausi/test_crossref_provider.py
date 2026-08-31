import pytest

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    RiskClass,
    SearchAction,
    VersionRef,
)
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.crossref import (
    CrossrefAdapter,
    crossref_policy_profile,
    register_crossref_adapter,
    register_crossref_policy,
    register_crossref_provider,
)
from ai_web_research.providers.registry import ProviderRegistry


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


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get(self, url, *, params=None, headers=None):
        self.calls.append((url, params or {}, headers or {}))
        return self.response


def make_action(top_k=3):
    return SearchAction(
        action_id="crossref-a1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.crossref", "1.0.0"),
        surface_id="surface.crossref.rest",
        binding_id="binding.lexical_search.crossref.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={
            "query": "autonomous research agents",
            "top_k": top_k,
            "from_pub_date": "2024-01-01",
        },
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def test_crossref_provider_and_binding_register_against_core_method():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_crossref_provider(providers, methods.snapshot())

    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.crossref", "1.0.0"))
    assert provider.kind.value == "academic"
    surface = snapshot.surface(VersionRef("provider.crossref", "1.0.0"), "surface.crossref.rest")
    assert "capability.lexical" in surface.capabilities
    binding = snapshot.get_binding("binding.lexical_search.crossref.v1")
    assert binding.adapter_id == "crossref.rest"


@pytest.mark.asyncio
async def test_crossref_adapter_maps_structured_metadata_to_candidate_observation():
    response = FakeResponse(
        {
            "status": "ok",
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/example",
                        "title": ["A Paper"],
                        "container-title": ["Journal"],
                        "publisher": "Publisher",
                        "type": "journal-article",
                        "URL": "https://doi.org/10.1000/example",
                        "published": {"date-parts": [[2025, 5, 1]]},
                        "author": [
                            {"given": "Ada", "family": "Lovelace"},
                            {"family": "Turing"},
                        ],
                    }
                ]
            },
        },
        headers={
            "x-rate-limit-limit": "1",
            "x-rate-limit-interval": "1s",
            "x-concurrency-limit": "1",
        },
    )
    client = FakeClient(response)
    adapter = CrossrefAdapter()
    action = make_action()
    from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, PolicyDecision
    authorized = AuthorizedAction(
        action=action,
        authorization=AuthorizationResult(PolicyDecision.ALLOW),
    )
    ctx = ExecutionContext(
        task_id="task-1",
        epoch_id="epoch-1",
        registry_snapshot_id="snapshot",
        services={
            "crossref_http_client": client,
            "crossref_mailto": "research@example.com",
        },
        runtime_limits={},
    )
    obs = await adapter.execute(authorized, ctx)
    assert obs.status.value == "succeeded"
    assert obs.result_count == 1
    assert obs.artifacts[0].kind is ArtifactKind.CANDIDATE
    meta = obs.artifacts[0].metadata
    assert meta["doi"] == "10.1000/example"
    assert meta["title"] == "A Paper"
    assert meta["authors"] == ["Ada Lovelace", "Turing"]
    assert meta["source_type"] == "crossref_metadata"
    assert meta["external_source"] is True
    assert meta["score_semantics"] == "crossref_provider_order"

    url, params, headers = client.calls[0]
    assert url.endswith("/works")
    assert params["query.bibliographic"] == "autonomous research agents"
    assert params["rows"] == 3
    assert params["mailto"] == "research@example.com"
    assert "abstract" not in params["select"]
    assert params["filter"] == "from-pub-date:2024-01-01"
    assert obs.metadata["rate_limit"]["limit"] == "1"
    assert obs.metadata["rate_limit"]["concurrency"] == "1"


@pytest.mark.asyncio
async def test_crossref_adapter_caps_rows_and_rejects_empty_query():
    adapter = CrossrefAdapter()
    from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, PolicyDecision
    response = FakeResponse({"status": "ok", "message": {"items": []}})
    client = FakeClient(response)
    action = make_action(top_k=500)
    authorized = AuthorizedAction(action, AuthorizationResult(PolicyDecision.ALLOW))
    ctx = ExecutionContext(
        task_id="task-1", epoch_id="epoch-1", registry_snapshot_id="s",
        services={"crossref_http_client": client}, runtime_limits={}
    )
    await adapter.execute(authorized, ctx)
    assert client.calls[0][1]["rows"] == 20

    bad = SearchAction(
        **{**action.__dict__, "parameters": {"query": "   "}}
    )
    with pytest.raises(Exception):
        await adapter.execute(
            AuthorizedAction(bad, AuthorizationResult(PolicyDecision.ALLOW)),
            ctx,
        )


def test_crossref_policy_allows_machine_query_and_carries_conservative_downstream_rights():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_crossref_provider(providers, methods.snapshot())
    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.crossref", "1.0.0"))
    surface = snapshot.surface(VersionRef("provider.crossref", "1.0.0"), "surface.crossref.rest")

    profile = crossref_policy_profile()
    registry = SourcePolicyRegistry()
    registry.register(profile)
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(),
        provider,
        surface,
        PolicyContext(
            task_id="task-1",
            purpose="research",
            party_profile_id=None,
            risk_class=RiskClass.LOW,
            jurisdiction_context=(),
            requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
            timestamp="2026-08-31T12:00:00+00:00",
        ),
        registry.snapshot().profiles_for("provider.crossref", "surface.crossref.rest"),
    )
    assert result.authorization.decision.value == "allow_with_obligations"
    assert AcquisitionAction.AUTOMATED_QUERY in result.usage_seed.permissions
    assert AcquisitionAction.INTERNAL_USE in result.usage_seed.permissions
    assert AcquisitionAction.PERSISTENT_CACHE in result.usage_seed.permissions
    assert AcquisitionAction.INDEX in result.usage_seed.permissions
    assert AcquisitionAction.REDISTRIBUTE_RAW not in result.usage_seed.permissions
    assert any(limit.kind == "crossref_public_list_rate" for limit in result.usage_seed.limits)


def test_crossref_convenience_registration_and_rate_provenance():
    from ai_web_research.execution.registry import AdapterRegistry
    policy_registry = SourcePolicyRegistry()
    register_crossref_policy(policy_registry)
    profile = policy_registry.latest("policy.crossref.rest.metadata")
    source_ids = {source.source_id for source in profile.policy_sources}
    assert "policy-source.crossref.rate-2025-12" in source_ids

    adapters = AdapterRegistry()
    register_crossref_adapter(adapters)
    resolved = adapters.get("crossref.rest", "1.0.0")
    assert isinstance(resolved, CrossrefAdapter)
