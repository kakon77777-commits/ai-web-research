import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizedAction, AuthorizationResult, ExecutionContext, PolicyDecision
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.methods.spec import (
    ContractSpec, EvidenceEffect, InteractionMode, MethodAvailability, MethodGoal,
    RepresentationKind, SearchDirection, SearchMethodSpec,
)
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.brave_search import (
    BRAVE_BINDING_ID, BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION, BRAVE_SURFACE_ID,
    BraveSearchAdapter, BraveSearchCredentialError, register_brave_search_provider,
)


def lexical_methods():
    spec = SearchMethodSpec(
        method_id='method.lexical_search', version='1.0.0', availability=MethodAvailability.AVAILABLE,
        aliases=(), purpose='lexical search', goals=frozenset({MethodGoal.DISCOVER}),
        representations=frozenset({RepresentationKind.LEXICAL}), directions=frozenset({SearchDirection.OUTWARD}),
        interaction_modes=frozenset({InteractionMode.ONE_SHOT}), evidence_effects=frozenset({EvidenceEffect.CANDIDATE}),
        input_contract=ContractSpec(accepts=frozenset({ArtifactKind.QUERY})),
        output_contract=ContractSpec(produces=frozenset({ArtifactKind.CANDIDATE_SET})),
        parameter_schema={}, required_capabilities=frozenset({'capability.lexical'}), preconditions=(), postconditions=(),
        failure_modes=(), cost_prior={}, latency_prior={}, receipt_requirements=(), stopping_implications=(), metadata={},
    )
    return MethodRegistrySnapshot('methods', (spec,))


def action():
    raw = SearchAction(
        action_id='a1', task_id='t1', epoch_id='e1', method_ref=VersionRef('method.lexical_search','1.0.0'),
        provider_ref=VersionRef(BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION), surface_id=BRAVE_SURFACE_ID,
        binding_id=BRAVE_BINDING_ID, action_kind=ActionKind.SEARCH, inputs=(),
        parameters={'query':'Model X release','top_k':3,'country':'TW','search_lang':'zh-hant'}, guards=(), expected_effects=(),
        created_by='test', created_at='2026-08-31T15:00:00+00:00',
    )
    return AuthorizedAction(raw, AuthorizationResult(PolicyDecision.ALLOW))


class FakeResponse:
    headers = {'x-ratelimit-limit':'50'}
    def raise_for_status(self): pass
    def json(self):
        return {'web': {'results': [
            {'url':'https://official.example/model-x','title':'Model X','description':'Official release'},
            {'url':'https://media.example/a','title':'Media A','description':'Reported release'},
        ]}}


class FakeClient:
    def __init__(self): self.calls=[]
    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class ExplodingClient:
    async def get(self, *args, **kwargs):
        raise AssertionError('transport must not be called')


def test_registers_search_engine_binding():
    registry=ProviderRegistry()
    register_brave_search_provider(registry, lexical_methods())
    provider=registry.get_provider(VersionRef(BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION))
    binding=registry.get_binding(BRAVE_BINDING_ID)
    assert provider.kind.value == 'search_engine'
    assert provider.surfaces[0].auth_profile == 'brave_search_api_key'
    assert binding.method_ref == VersionRef('method.lexical_search','1.0.0')


@pytest.mark.asyncio
async def test_missing_credential_fails_before_transport():
    adapter=BraveSearchAdapter()
    ctx=ExecutionContext('t1','e1','snap',services={'brave_search_http_client':ExplodingClient()})
    with pytest.raises(BraveSearchCredentialError):
        await adapter.execute(action(), ctx)


@pytest.mark.asyncio
async def test_sends_auth_header_and_query_params():
    client=FakeClient(); adapter=BraveSearchAdapter()
    ctx=ExecutionContext('t1','e1','snap',services={'brave_search_http_client':client,'brave_search_api_key':'secret-key','clock':'2026-08-31T15:01:00+00:00'})
    await adapter.execute(action(), ctx)
    url, kwargs=client.calls[0]
    assert url.endswith('/res/v1/web/search')
    assert kwargs['headers']['X-Subscription-Token'] == 'secret-key'
    assert kwargs['params'] == {'q':'Model X release','count':3,'country':'TW','search_lang':'zh-hant'}


@pytest.mark.asyncio
async def test_normalizes_candidates_as_discovery_only():
    client=FakeClient(); adapter=BraveSearchAdapter()
    ctx=ExecutionContext('t1','e1','snap',services={'brave_search_http_client':client,'brave_search_api_key':'secret-key','clock':'2026-08-31T15:01:00+00:00'})
    obs=await adapter.execute(action(), ctx)
    assert obs.result_count == 2
    first=obs.artifacts[0]
    assert first.kind is ArtifactKind.CANDIDATE
    assert first.metadata['url'] == 'https://official.example/model-x'
    assert first.metadata['provider_rank'] == 1
    assert first.metadata['source_type'] == 'brave_web_search_result'
    assert first.metadata['evidence_role'] == 'discovery_only'
    assert 'secret-key' not in repr(obs)


@pytest.mark.asyncio
async def test_top_k_is_clamped_to_twenty():
    client=FakeClient(); adapter=BraveSearchAdapter()
    auth=action()
    raw=auth.action
    raw2=SearchAction(**{**raw.__dict__, 'parameters': {'query':'x','top_k':999}})
    ctx=ExecutionContext('t1','e1','snap',services={'brave_search_http_client':client,'brave_search_api_key':'secret'})
    await adapter.execute(AuthorizedAction(raw2, auth.authorization), ctx)
    assert client.calls[0][1]['params']['count'] == 20
