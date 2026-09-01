import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.patents.epo_ops import (
    EpoOpsAdapter,
    EpoOpsAuthError,
    register_epo_ops_adapter,
    register_epo_ops_policy,
    register_epo_ops_provider,
)
from ai_web_research.providers.registry import ProviderRegistry


OPS_XML = """<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:exchange="http://www.epo.org/exchange">
<ops:biblio-search><ops:search-result><exchange:exchange-documents>
<exchange:exchange-document country="EP" doc-number="1234567" kind="A1"><exchange:bibliographic-data>
<exchange:publication-reference><exchange:document-id document-id-type="docdb">
<exchange:country>EP</exchange:country><exchange:doc-number>1234567</exchange:doc-number>
<exchange:kind>A1</exchange:kind><exchange:date>20260115</exchange:date>
</exchange:document-id></exchange:publication-reference>
<exchange:application-reference><exchange:document-id document-id-type="docdb">
<exchange:country>EP</exchange:country><exchange:doc-number>25123456</exchange:doc-number><exchange:kind>A</exchange:kind>
</exchange:document-id></exchange:application-reference>
<exchange:priority-claims><exchange:priority-claim><exchange:document-id document-id-type="epodoc">
<exchange:country>US</exchange:country><exchange:doc-number>20240123456</exchange:doc-number><exchange:date>20240110</exchange:date>
</exchange:document-id></exchange:priority-claim></exchange:priority-claims>
<exchange:parties><exchange:applicants><exchange:applicant><exchange:applicant-name><exchange:name>Example Corp</exchange:name>
</exchange:applicant-name></exchange:applicant></exchange:applicants><exchange:inventors><exchange:inventor><exchange:inventor-name>
<exchange:name>Ada Inventor</exchange:name></exchange:inventor-name></exchange:inventor></exchange:inventors></exchange:parties>
<exchange:invention-title lang="en">Autonomous patent search</exchange:invention-title>
<exchange:classifications-cpc><exchange:classification-cpc><exchange:text>G06F16/24578</exchange:text>
</exchange:classification-cpc></exchange:classifications-cpc>
<exchange:classifications-ipcr><exchange:classification-ipcr><exchange:text>G06F 16/245</exchange:text>
</exchange:classification-ipcr></exchange:classifications-ipcr>
</exchange:bibliographic-data></exchange:exchange-document>
</exchange:exchange-documents></ops:search-result></ops:biblio-search></ops:world-patent-data>"""


class FakeResponse:
    status_code = 200
    headers = {"x-individualquotaperhour-used": "2"}
    text = OPS_XML

    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, *, params=None, headers=None):
        self.calls.append((url, params or {}, headers or {}))
        return FakeResponse()


def registries():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    register_patent_methods(methods)
    providers = ProviderRegistry()
    register_epo_ops_provider(providers, methods.snapshot())
    return methods, providers


def search_action(method="method.lexical_search", binding="binding.lexical_search.epo_ops.v1", parameters=None):
    return SearchAction(
        "epo-a", "task", "epoch", VersionRef(method, "1.0.0"), VersionRef("provider.epo_ops", "1.0.0"),
        "surface.epo_ops.rest", binding, ActionKind.SEARCH, (ArtifactRef(ArtifactKind.QUERY, "q"),),
        parameters or {"query": "autonomous patent search", "range": "1-10"}, (), ("candidate_set_created",),
        "planner.rule.v0", "2026-08-31T12:00:00+00:00",
    )


def authorized(action):
    return AuthorizedAction(action, AuthorizationResult(PolicyDecision.ALLOW), credential_profile_id="credential.epo_ops")


def context(client, token="token"):
    services = {"epo_ops_http_client": client}
    if token is not None:
        services["epo_ops_access_token"] = token
    return ExecutionContext("task", "epoch", "snapshot", services, {})


def test_epo_registry_has_core_and_patent_bindings():
    methods, providers = registries()
    snapshot = providers.snapshot()
    surface = snapshot.surface(VersionRef("provider.epo_ops", "1.0.0"), "surface.epo_ops.rest")
    assert methods.latest("method.patent.classification_search").metadata["domain"] == "patent_intelligence"
    assert surface.kind.value == "authenticated_api"
    assert surface.auth_profile == "oauth2.epo_ops"
    assert snapshot.get_binding("binding.lexical_search.epo_ops.v1").adapter_id == "epo.ops"
    assert snapshot.get_binding("binding.patent_classification.epo_ops.v1").adapter_id == "epo.ops"


@pytest.mark.asyncio
async def test_epo_lexical_search_normalizes_bibliographic_metadata():
    client = FakeClient()
    obs = await EpoOpsAdapter().execute(authorized(search_action()), context(client))
    item = obs.artifacts[0]
    assert item.id == "epo:publication:EP1234567A1"
    assert item.metadata["application_number"] == "EP25123456A"
    assert item.metadata["publication_date"] == "2026-01-15"
    assert item.metadata["priority_dates"] == ["2024-01-10"]
    assert item.metadata["applicants"] == ["Example Corp"]
    assert item.metadata["inventors"] == ["Ada Inventor"]
    assert item.metadata["cpc"] == ["G06F16/24578"]
    assert item.metadata["ipc"] == ["G06F16/245"]
    assert client.calls[0][1]["q"] == 'ta all "autonomous patent search"'
    assert client.calls[0][2]["Authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_epo_classification_search_generates_cql_and_caps_range():
    client = FakeClient()
    action = search_action(
        "method.patent.classification_search",
        "binding.patent_classification.epo_ops.v1",
        {"classification": "G06F16/00", "scheme": "cpc", "range": "1-500"},
    )
    await EpoOpsAdapter().execute(authorized(action), context(client))
    assert client.calls[0][1] == {"q": "cpc=G06F16/00", "Range": "1-100"}


@pytest.mark.asyncio
async def test_epo_requires_oauth_before_transport():
    client = FakeClient()
    with pytest.raises(EpoOpsAuthError):
        await EpoOpsAdapter().execute(authorized(search_action()), context(client, token=None))
    assert client.calls == []


def test_epo_policy_carries_usage_rights_and_raw_redistribution_prohibition():
    _, providers = registries()
    snapshot = providers.snapshot()
    policies = SourcePolicyRegistry()
    register_epo_ops_policy(policies)
    profile = policies.latest("policy.epo_ops.rest")
    evaluation = DeterministicPolicyEvaluator().evaluate(
        search_action(),
        snapshot.get_provider(VersionRef("provider.epo_ops", "1.0.0")),
        snapshot.surface(VersionRef("provider.epo_ops", "1.0.0"), "surface.epo_ops.rest"),
        PolicyContext("task", "research", None, RiskClass.HIGH, ("EP",), (AcquisitionAction.AUTOMATED_QUERY,), "2026-08-31T12:00:00+00:00"),
        policies.snapshot().profiles_for("provider.epo_ops", "surface.epo_ops.rest"),
    )
    assert profile.auth_requirements["oauth2"] is True
    assert profile.rate_limits["family_requests_per_second"] == 1
    assert profile.rate_limits["free_gb_per_week"] == 4
    assert AcquisitionAction.INTERNAL_USE in evaluation.usage_seed.permissions
    assert AcquisitionAction.COMMERCIAL_USE in evaluation.usage_seed.permissions
    assert AcquisitionAction.DISTRIBUTE_DERIVED in evaluation.usage_seed.permissions
    assert AcquisitionAction.REDISTRIBUTE_RAW in evaluation.usage_seed.prohibitions


def test_epo_adapter_registration_is_exact_versioned():
    from ai_web_research.execution.registry import AdapterRegistry

    registry = AdapterRegistry()
    register_epo_ops_adapter(registry)
    assert isinstance(registry.get("epo.ops", "1.0.0"), EpoOpsAdapter)
