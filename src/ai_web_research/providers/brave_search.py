from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Mapping

from ai_web_research.core.types import ArtifactKind, ArtifactRef, VersionRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.policy.models import AcquisitionAction, PolicyRule, PolicyRuleEffect, PolicySourceRef, SourcePolicyProfile
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind

BRAVE_PROVIDER_ID = 'provider.brave_search'
BRAVE_PROVIDER_VERSION = '1.0.0'
BRAVE_SURFACE_ID = 'surface.brave_search.web'
BRAVE_ADAPTER_ID = 'brave_search.web'
BRAVE_ADAPTER_VERSION = '1.0.0'
BRAVE_BINDING_ID = 'binding.lexical_search.brave_search.v1'
BRAVE_BASE_URL = 'https://api.search.brave.com'


class BraveSearchAdapterError(RuntimeError):
    pass


class BraveSearchCredentialError(BraveSearchAdapterError):
    pass


def _policy_hash(rules: tuple[PolicyRule, ...]) -> str:
    payload = [
        {'id': r.rule_id, 'action': r.action.value, 'effect': r.effect.value, 'value': r.value, 'constraints': r.constraints}
        for r in rules
    ]
    return sha256(dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def brave_search_policy_profile() -> SourcePolicyProfile:
    docs = PolicySourceRef(
        source_id='policy-source.brave-search.auth',
        uri='https://api-dashboard.search.brave.com/documentation/guides/authentication',
        title='Brave Search API Authentication',
        retrieved_at='2026-08-31T15:00:00+00:00', effective_at=None, expires_at=None,
        content_hash=None, anchor={'section':'Authentication Method'}, authority='provider',
        interpretation_status='provider_human_readable',
    )
    ref = PolicySourceRef(
        source_id='policy-source.brave-search.web',
        uri='https://api-dashboard.search.brave.com/api-reference/web/search/get',
        title='Brave Search API Web Search',
        retrieved_at='2026-08-31T15:00:00+00:00', effective_at=None, expires_at=None,
        content_hash=None, anchor={'section':'GET /v1/web/search'}, authority='provider',
        interpretation_status='provider_human_readable',
    )
    pricing = PolicySourceRef(
        source_id='policy-source.brave-search.pricing',
        uri='https://api-dashboard.search.brave.com/documentation/pricing',
        title='Brave Search API Pricing',
        retrieved_at='2026-08-31T15:00:00+00:00', effective_at=None, expires_at=None,
        content_hash=None, anchor={'section':'Search'}, authority='provider',
        interpretation_status='provider_human_readable',
    )
    rules = (
        PolicyRule(
            rule_id='brave-search-allow-automated-query', action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.PERMISSION, value=True, asset_scope='web_search_candidate_metadata',
            party_scope=None, purpose_scope=(), constraints={}, source_refs=(ref.source_id,), priority_hint=10,
        ),
        PolicyRule(
            rule_id='brave-search-capacity', action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT, value=50, asset_scope='web_search_request',
            party_scope=None, purpose_scope=(), constraints={'unit':'requests','window':'second'},
            source_refs=(pricing.source_id,), priority_hint=20,
        ),
    )
    return SourcePolicyProfile(
        policy_id='policy.brave_search.web', version='1.0.0', provider_id=BRAVE_PROVIDER_ID,
        surface_id=BRAVE_SURFACE_ID, asset_scope='web_search_candidate_metadata', rules=rules,
        policy_sources=(docs, ref, pricing), auth_requirements={'header':'X-Subscription-Token','credential_required':True},
        rate_limits={'documented_product_capacity_requests_per_second':50}, retention_rules={},
        attribution_rules={}, redistribution_rules={'persistent_redistribution':'not_asserted_by_builtin_profile'},
        privacy_flags=(), observed_at='2026-08-31T15:00:00+00:00', effective_at=None, expires_at=None,
        next_review_at='2026-09-30T00:00:00+00:00', policy_hash=_policy_hash(rules),
        review_status='provider_documented', metadata={'evidence_role':'discovery_only'},
    )


def register_brave_search_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    provider = ProviderSpec(
        provider_id=BRAVE_PROVIDER_ID, version=BRAVE_PROVIDER_VERSION, kind=ProviderKind.SEARCH_ENGINE,
        display_name='Brave Search API', domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id=BRAVE_SURFACE_ID, kind=SurfaceKind.AUTHENTICATED_API,
            endpoint_ref=f'{BRAVE_BASE_URL}/res/v1/web/search', capabilities=frozenset({'capability.lexical'}),
            auth_profile='brave_search_api_key', policy_profile_refs=('policy.brave_search.web@1.0.0',),
            static_limits={'documented_product_capacity_requests_per_second':50},
            metadata={'structured_format':'json','evidence_role':'discovery_only'},
        ),), metadata={'official_docs':'https://api-dashboard.search.brave.com/api-reference/web/search/get'},
    )
    registry.register_provider(provider)
    registry.register_binding(MethodBinding(
        binding_id=BRAVE_BINDING_ID, method_ref=VersionRef('method.lexical_search','1.0.0'),
        provider_ref=VersionRef(BRAVE_PROVIDER_ID,BRAVE_PROVIDER_VERSION), surface_id=BRAVE_SURFACE_ID,
        adapter_id=BRAVE_ADAPTER_ID, adapter_version=BRAVE_ADAPTER_VERSION, enabled=True,
        parameter_mapping={}, metadata={'endpoint':'/res/v1/web/search','query_parameter':'q'},
    ), methods)


def register_brave_search_policy(registry) -> None:
    registry.register(brave_search_policy_profile())


def register_brave_search_adapter(registry) -> None:
    registry.register(BraveSearchAdapter())


class BraveSearchAdapter:
    adapter_id = BRAVE_ADAPTER_ID
    adapter_version = BRAVE_ADAPTER_VERSION

    async def _get(self, context: ExecutionContext, token: str, params: dict[str, object]):
        client = context.services.get('brave_search_http_client')
        close_client = False
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=20.0)
            close_client = True
        try:
            return await client.get(
                f'{BRAVE_BASE_URL}/res/v1/web/search', params=params,
                headers={'Accept':'application/json','X-Subscription-Token':token},
            )
        finally:
            if close_client:
                await client.aclose()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw = action.action
        if raw.method_ref != VersionRef('method.lexical_search','1.0.0'):
            raise BraveSearchAdapterError(f'unsupported method: {raw.method_ref}')
        if raw.provider_ref != VersionRef(BRAVE_PROVIDER_ID, BRAVE_PROVIDER_VERSION):
            raise BraveSearchAdapterError(f'wrong provider: {raw.provider_ref}')
        if raw.surface_id != BRAVE_SURFACE_ID or raw.binding_id != BRAVE_BINDING_ID:
            raise BraveSearchAdapterError('action does not match Brave Search binding')
        token = context.services.get('brave_search_api_key')
        if not isinstance(token, str) or not token.strip():
            raise BraveSearchCredentialError('brave_search_api_key is required')
        query = raw.parameters.get('query')
        if not isinstance(query, str) or not query.strip():
            raise BraveSearchAdapterError('Brave search requires non-empty query')
        top_k_raw = raw.parameters.get('top_k', 10)
        if isinstance(top_k_raw, bool) or not isinstance(top_k_raw, int):
            raise BraveSearchAdapterError('top_k must be an integer')
        params: dict[str, object] = {'q':query.strip(), 'count':max(1,min(top_k_raw,20))}
        for key in ('country','search_lang'):
            value = raw.parameters.get(key)
            if isinstance(value, str) and value.strip(): params[key]=value.strip()
        response = await self._get(context, token.strip(), params)
        try:
            response.raise_for_status(); payload = response.json()
        except Exception as exc:
            raise BraveSearchAdapterError(f'Brave Search request failed: {exc}') from exc
        if not isinstance(payload, Mapping):
            raise BraveSearchAdapterError('Brave Search response is not an object')
        web = payload.get('web')
        results = web.get('results') if isinstance(web, Mapping) else []
        if results is None: results=[]
        if not isinstance(results, list):
            raise BraveSearchAdapterError('Brave Search web.results is not a list')
        artifacts=[]
        for index, item in enumerate(results, start=1):
            if not isinstance(item, Mapping): continue
            url=item.get('url')
            if not isinstance(url, str) or not url.strip(): continue
            normalized_url=url.strip()
            aid='brave:url:'+sha256(normalized_url.encode('utf-8')).hexdigest()[:24]
            artifacts.append(ArtifactRef(
                ArtifactKind.CANDIDATE, aid, metadata={
                    'url':normalized_url,
                    'title': str(item.get('title')) if item.get('title') is not None else None,
                    'description': str(item.get('description')) if item.get('description') is not None else None,
                    'provider_rank':index,
                    'source_type':'brave_web_search_result',
                    'external_source':True,
                    'evidence_role':'discovery_only',
                }
            ))
        return ProviderObservation(
            observation_id=f'{raw.action_id}:observation:brave_search', action_id=raw.action_id,
            provider_id=BRAVE_PROVIDER_ID, surface_id=BRAVE_SURFACE_ID, status=ObservationStatus.SUCCEEDED,
            artifacts=tuple(artifacts), raw_ref=None, result_count=len(artifacts), cost={}, latency_ms=None,
            continuation={}, diagnostics=(), occurred_at=str(context.services.get('clock') or raw.created_at),
            metadata={'query':query.strip(),'evidence_role':'discovery_only'},
        )
