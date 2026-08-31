import pytest

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    RiskClass,
    SearchAction,
    VersionRef,
)
from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.execution.models import (
    AuthorizationResult,
    AuthorizedAction,
    ExecutionContext,
    PolicyDecision,
)
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.patents.epo_ops import (
    EpoOpsAdapter,
    EpoOpsAuthError,
    epo_ops_policy_profile,
    register_epo_ops_adapter,
    register_epo_ops_policy,
    register_epo_ops_provider,
)
from ai_web_research.providers.registry import ProviderRegistry


OPS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org"
  xmlns:exchange="http://www.epo.org/exchange">
  <ops:biblio-search total-result-count="1">
    <ops:search-result>
      <exchange:exchange-documents>
        <exchange:exchange-document country="EP" doc-number="1234567" kind="A1">
          <exchange:bibliographic-data>
            <exchange:publication-reference>
              <exchange:document-id document-id-type="docdb">
                <exchange:country>EP</exchange:country>
                <exchange:doc-number>1234567</exchange:doc-number>
                <exchange:kind>A1</exchange:kind>
                <exchange:date>20260115</exchange:date>
              </exchange:document-id>
            </exchange:publication-reference>
            <exchange:application-reference>
              <exchange:document-id document-id-type="docdb">
                <exchange:country>EP</exchange:country>
                <exchange:doc-number>25123456</exchange:doc-number>
                <exchange:kind>A</exchange:kind>
                <exchange:date>20250701</exchange:date>
              </exchange:document-id>
            </exchange:application-reference>
            <exchange:priority-claims>
              <exchange:priority-claim sequence="1">
                <exchange:document-id document-id-type="epodoc">
                  <exchange:country>US</exchange:country>
                  <exchange:doc-number>20240123456</exchange:doc-number>
                  <exchange:date>20240110</exchange:date>
                </exchange:document-id>
              </exchange:priority-claim>
            </exchange:priority-claims>
            <exchange:parties>
              <exchange:applicants>
                <exchange:applicant sequence="1" data-format="epodoc">
                  <exchange:applicant-name><exchange:name>Example Corp</exchange:name></exchange:applicant-name>
                </exchange:applicant>
              </exchange:applicants>
              <exchange:inventors>
                <exchange:inventor sequence="1" data-format="epodoc">
                  <exchange:inventor-name><exchange:name>Ada Inventor</exchange:name></exchange:inventor-name>
                </exchange:inventor>
              </exchange:inventors>
            </exchange:parties>
            <exchange:invention-title lang="en">Autonomous patent search</exchange:invention-title>
            <exchange:classifications-cpc>
              <exchange:classification-cpc sequence="1">
                <exchange:text>G06F16/24578</exchange:text>
              </exchange:classification-cpc>
            </exchange:classifications-cpc>
            <exchange:classifications-ipcr>
              <exchange:classification-ipcr sequence="1">
                <exchange:text>G06F 16/245</exchange:text>
              </exchange:classification-ipcr>
            </exchange:classifications-ipcr>
          </exchange:bibliographic-data>
        </exchange:exchange-document>
      </exchange:exchange-documents>
    </ops:search-result>
  </ops:biblio-search>
</ops:world-patent-data>
"""


class FakeResponse:
    def __init__(self, text=OPS_XML, status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"x-individualquotaperhour-used": "2"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeClient:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.calls = []

    async def get(self, url, *, params=None, headers=None):
        self.calls.append((url, params or {}, headers or {}))
        return self.response


def build_registries():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    register_patent_methods(methods)

    providers = ProviderRegistry()
    register_epo_ops_provider(providers, methods.snapshot())
    return methods, providers


def lexical_action():
    return SearchAction(
        action_id="epo-search-1",
        task_id="task-patent",
        epoch_id="epoch-patent",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.epo_ops", "1.0.0"),
        surface_id="surface.epo_ops.rest",
        binding_id="binding.lexical_search.epo_ops.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={
            "query": "autonomous patent search",
            "range": "1-10",
        },
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def classification_action():
    return SearchAction(
        action_id="epo-class-1",
        task_id="task-patent",
        epoch_id="epoch-patent",
        method_ref=VersionRef("method.patent.classification_search", "1.0.0"),
        provider_ref=VersionRef("provider.epo_ops", "1.0.0"),
        surface_id="surface.epo_ops.rest",
        binding_id="binding.patent_classification.epo_ops.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "classification:G06F16/00"),),
        parameters={
            "classification": "G06F16/00",
            "scheme": "cpc",
            "range": "1-5",
        },
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def authorized(action):
    return AuthorizedAction(
        action,
        AuthorizationResult(PolicyDecision.ALLOW),
        credential_profile_id="credential.epo_ops",
    )


def context(client, token="token-123"):
    services = {"epo_ops_http_client": client}
    if token is not None:
        services["epo_ops_access_token"] = token
    return ExecutionContext(
        task_id="task-patent",
        epoch_id="epoch-patent",
        registry_snapshot_id="snapshot",
        services=services,
        runtime_limits={},
    )


def test_patent_method_and_epo_bindings_register_without_polluting_core_ids():
    methods, providers = build_registries()
    assert methods.latest("method.patent.classification_search").method_id == "method.patent.classification_search"

    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.epo_ops", "1.0.0"))
    assert provider.kind.value == "patent"
    surface = snapshot.surface(VersionRef("provider.epo_ops", "1.0.0"), "surface.epo_ops.rest")
    assert surface.kind.value == "authenticated_api"
    assert surface.auth_profile == "oauth2.epo_ops"
    assert "capability.lexical" in surface.capabilities
    assert "capability.taxonomy_filter" in surface.capabilities
    assert snapshot.get_binding("binding.lexical_search.epo_ops.v1").adapter_id == "epo.ops"
    assert snapshot.get_binding("binding.patent_classification.epo_ops.v1").adapter_id == "epo.ops"


@pytest.mark.asyncio
async def test_epo_ops_lexical_search_uses_oauth_cql_and_normalizes_patent_candidate_metadata():
    client = FakeClient()
    adapter = EpoOpsAdapter()
    obs = await adapter.execute(authorized(lexical_action()), context(client))
    assert obs.result_count == 1
    artifact = obs.artifacts[0]
    assert artifact.kind is ArtifactKind.CANDIDATE
    assert artifact.id == "epo:publication:EP1234567A1"
    meta = artifact.metadata
    assert meta["publication_number"] == "EP1234567A1"
    assert meta["application_number"] == "EP25123456A"
    assert meta["title"] == "Autonomous patent search"
    assert meta["publication_date"] == "2026-01-15"
    assert meta["priority_dates"] == ["2024-01-10"]
    assert meta["applicants"] == ["Example Corp"]
    assert meta["inventors"] == ["Ada Inventor"]
    assert "G06F16/24578" in meta["cpc"]
    assert "G06F16/245" in meta["ipc"]
    assert meta["source_type"] == "epo_ops_bibliographic"
    assert meta["external_source"] is True
    assert meta["score_semantics"] == "epo_ops_provider_order"

    url, params, headers = client.calls[0]
    assert url.endswith("/published-data/search")
    assert params["q"] == 'ta all "autonomous patent search"'
    assert headers["Authorization"] == "Bearer token-123"
    assert headers["Accept"] == "application/xml"


@pytest.mark.asyncio
async def test_epo_ops_classification_search_generates_cql_and_enforces_range_limit():
    client = FakeClient()
    adapter = EpoOpsAdapter()
    action = classification_action()
    action = SearchAction(**{**action.__dict__, "parameters": {**action.parameters, "range": "1-500"}})
    await adapter.execute(authorized(action), context(client))
    _, params, _ = client.calls[0]
    assert params["q"] == "cpc=G06F16/00"
    assert params["Range"] == "1-100"


@pytest.mark.asyncio
async def test_epo_ops_requires_oauth_access_token_before_transport():
    client = FakeClient()
    with pytest.raises(EpoOpsAuthError):
        await EpoOpsAdapter().execute(authorized(lexical_action()), context(client, token=None))
    assert client.calls == []


def test_epo_ops_policy_requires_auth_allows_derived_product_use_and_denies_raw_redistribution():
    methods, providers = build_registries()
    snapshot = providers.snapshot()
    provider = snapshot.get_provider(VersionRef("provider.epo_ops", "1.0.0"))
    surface = snapshot.surface(VersionRef("provider.epo_ops", "1.0.0"), "surface.epo_ops.rest")

    policies = SourcePolicyRegistry()
    register_epo_ops_policy(policies)
    profile = policies.latest("policy.epo_ops.rest")
    assert profile.auth_requirements["oauth2"] is True
    assert profile.rate_limits["family_requests_per_second"] == 1
    assert profile.rate_limits["free_gb_per_week"] == 4
    assert "raw_data_public_redistribution" in profile.redistribution_rules

    evaluation = DeterministicPolicyEvaluator().evaluate(
        lexical_action(),
        provider,
        surface,
        PolicyContext(
            task_id="task-patent",
            purpose="research",
            party_profile_id=None,
            risk_class=RiskClass.HIGH,
            jurisdiction_context=("EP",),
            requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
            timestamp="2026-08-31T12:00:00+00:00",
        ),
        policies.snapshot().profiles_for("provider.epo_ops", "surface.epo_ops.rest"),
    )
    assert evaluation.authorization.decision.value == "allow_with_obligations"
    assert AcquisitionAction.AUTOMATED_QUERY in evaluation.usage_seed.permissions
    assert AcquisitionAction.INTERNAL_USE in evaluation.usage_seed.permissions
    assert AcquisitionAction.COMMERCIAL_USE in evaluation.usage_seed.permissions
    assert AcquisitionAction.DISTRIBUTE_DERIVED in evaluation.usage_seed.permissions
    assert AcquisitionAction.REDISTRIBUTE_RAW in evaluation.usage_seed.prohibitions


def test_epo_ops_adapter_registration_is_exact_versioned():
    from ai_web_research.execution.registry import AdapterRegistry

    registry = AdapterRegistry()
    register_epo_ops_adapter(registry)
    adapter = registry.get("epo.ops", "1.0.0")
    assert isinstance(adapter, EpoOpsAdapter)
