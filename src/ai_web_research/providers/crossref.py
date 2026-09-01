from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Mapping

from ai_web_research.core.types import ArtifactKind, ArtifactRef, VersionRef
from ai_web_research.execution.models import (
    AuthorizedAction,
    ExecutionContext,
    ObservationStatus,
    ProviderObservation,
)
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.policy.models import (
    AcquisitionAction,
    PolicyRule,
    PolicyRuleEffect,
    PolicySourceRef,
    SourcePolicyProfile,
)
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import (
    MethodBinding,
    ProviderKind,
    ProviderSpec,
    ProviderSurface,
    SurfaceKind,
)


CROSSREF_PROVIDER_ID = "provider.crossref"
CROSSREF_PROVIDER_VERSION = "1.0.0"
CROSSREF_SURFACE_ID = "surface.crossref.rest"
CROSSREF_ADAPTER_ID = "crossref.rest"
CROSSREF_ADAPTER_VERSION = "1.0.0"
CROSSREF_BINDING_ID = "binding.lexical_search.crossref.v1"
CROSSREF_BASE_URL = "https://api.crossref.org/v1"

_CROSSREF_SELECT = (
    "DOI,title,container-title,published,publisher,type,URL,author"
)


class CrossrefAdapterError(RuntimeError):
    pass


def _title(item: Mapping[str, object]) -> str | None:
    value = item.get("title")
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _container_title(item: Mapping[str, object]) -> str | None:
    value = item.get("container-title")
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _authors(item: Mapping[str, object]) -> list[str]:
    result: list[str] = []
    raw = item.get("author")
    if not isinstance(raw, list):
        return result
    for author in raw:
        if not isinstance(author, Mapping):
            continue
        parts = []
        given = author.get("given")
        family = author.get("family")
        if given:
            parts.append(str(given))
        if family:
            parts.append(str(family))
        if parts:
            result.append(" ".join(parts))
    return result


def _published(item: Mapping[str, object]) -> str | None:
    value = item.get("published")
    if not isinstance(value, Mapping):
        return None
    parts = value.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    values = parts[0]
    if not values:
        return None
    year = int(values[0])
    month = int(values[1]) if len(values) > 1 else 1
    day = int(values[2]) if len(values) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


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
    return sha256(
        dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def crossref_policy_profile() -> SourcePolicyProfile:
    source_rest = PolicySourceRef(
        source_id="policy-source.crossref.rest-api",
        uri="https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        title="Crossref REST API",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash=None,
        anchor={"section": "REST API"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    source_access = PolicySourceRef(
        source_id="policy-source.crossref.access",
        uri="https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/",
        title="Crossref REST API access and authentication",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash=None,
        anchor={"section": "Access and authentication"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )
    source_rate = PolicySourceRef(
        source_id="policy-source.crossref.rate-2025-12",
        uri="https://www.crossref.org/blog/announcing-changes-to-rest-api-rate-limits/",
        title="Announcing changes to REST API rate limits",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at="2025-12-01T00:00:00+00:00",
        expires_at=None,
        content_hash=None,
        anchor={"section": "Public pool / Polite pool list-of-record limits"},
        authority="provider",
        interpretation_status="provider_human_readable",
    )

    permissions = (
        AcquisitionAction.AUTOMATED_QUERY,
        AcquisitionAction.PERSISTENT_CACHE,
        AcquisitionAction.INDEX,
        AcquisitionAction.INTERNAL_USE,
        AcquisitionAction.COMMERCIAL_USE,
        AcquisitionAction.LINK,
    )
    rules: list[PolicyRule] = []
    for action in permissions:
        rules.append(
            PolicyRule(
                rule_id=f"crossref-allow-{action.value}",
                action=action,
                effect=PolicyRuleEffect.PERMISSION,
                value=True,
                asset_scope="bibliographic_metadata_without_abstract",
                party_scope=None,
                purpose_scope=(),
                constraints={},
                source_refs=("policy-source.crossref.rest-api",),
                priority_hint=10,
            )
        )
    rules.append(
        PolicyRule(
            rule_id="crossref_public_list_rate",
            action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT,
            value=1,
            asset_scope="works_list_query",
            party_scope=None,
            purpose_scope=(),
            constraints={"unit": "requests", "window": "second"},
            source_refs=("policy-source.crossref.rate-2025-12",),
            priority_hint=20,
        )
    )
    rules.append(
        PolicyRule(
            rule_id="crossref_public_list_concurrency",
            action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT,
            value=1,
            asset_scope="works_list_query",
            party_scope=None,
            purpose_scope=(),
            constraints={"unit": "requests", "window": "concurrent"},
            source_refs=("policy-source.crossref.rate-2025-12",),
            priority_hint=20,
        )
    )

    tuple_rules = tuple(rules)
    return SourcePolicyProfile(
        policy_id="policy.crossref.rest.metadata",
        version="1.0.0",
        provider_id=CROSSREF_PROVIDER_ID,
        surface_id=CROSSREF_SURFACE_ID,
        asset_scope="bibliographic_metadata_without_abstract",
        rules=tuple_rules,
        policy_sources=(source_rest, source_access, source_rate),
        auth_requirements={"public": True, "polite_mailto_optional": True},
        rate_limits={
            "public_list_requests_per_second": 1,
            "public_concurrency": 1,
            "polite_list_requests_per_second": 3,
            "polite_concurrency": 3,
        },
        retention_rules={},
        attribution_rules={},
        redistribution_rules={
            "raw_redistribution": "not_asserted_by_builtin_profile"
        },
        privacy_flags=(),
        observed_at="2026-08-31T12:00:00+00:00",
        effective_at=None,
        expires_at=None,
        next_review_at="2026-09-30T00:00:00+00:00",
        policy_hash=_policy_hash(tuple_rules),
        review_status="provider_documented",
        metadata={
            "abstracts_excluded": True,
            "notes": (
                "Built-in profile intentionally excludes abstract retrieval because "
                "Crossref notes that some abstracts may be copyrighted."
            ),
        },
    )


def register_crossref_provider(
    registry: ProviderRegistry,
    methods: MethodRegistrySnapshot,
) -> None:
    provider = ProviderSpec(
        provider_id=CROSSREF_PROVIDER_ID,
        version=CROSSREF_PROVIDER_VERSION,
        kind=ProviderKind.ACADEMIC,
        display_name="Crossref REST API",
        domains=("academic", "scholarly_metadata"),
        languages=(),
        jurisdictions=(),
        surfaces=(
            ProviderSurface(
                surface_id=CROSSREF_SURFACE_ID,
                kind=SurfaceKind.PUBLIC_API,
                endpoint_ref=CROSSREF_BASE_URL,
                capabilities=frozenset({
                    "capability.lexical",
                    "capability.date_filter",
                }),
                auth_profile=None,
                policy_profile_refs=("policy.crossref.rest.metadata@1.0.0",),
                static_limits={
                    "public_list_requests_per_second": 1,
                    "public_concurrency": 1,
                    "polite_list_requests_per_second": 3,
                    "polite_concurrency": 3,
                },
                metadata={
                    "structured_format": "json",
                    "abstracts_excluded_by_adapter": True,
                },
            ),
        ),
        metadata={"official_docs": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"},
    )
    registry.register_provider(provider)
    registry.register_binding(
        MethodBinding(
            binding_id=CROSSREF_BINDING_ID,
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(CROSSREF_PROVIDER_ID, CROSSREF_PROVIDER_VERSION),
            surface_id=CROSSREF_SURFACE_ID,
            adapter_id=CROSSREF_ADAPTER_ID,
            adapter_version=CROSSREF_ADAPTER_VERSION,
            enabled=True,
            parameter_mapping={},
            metadata={
                "endpoint": "/works",
                "query_parameter": "query.bibliographic",
            },
        ),
        methods,
    )


def register_crossref_policy(registry) -> None:
    registry.register(crossref_policy_profile())


def register_crossref_adapter(registry) -> None:
    registry.register(CrossrefAdapter())


class CrossrefAdapter:
    adapter_id = CROSSREF_ADAPTER_ID
    adapter_version = CROSSREF_ADAPTER_VERSION

    async def _get(self, context: ExecutionContext, params: dict[str, object]):
        client = context.services.get("crossref_http_client")
        close_client = False
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=20.0)
            close_client = True
        try:
            return await client.get(
                f"{CROSSREF_BASE_URL}/works",
                params=params,
                headers={"User-Agent": "ai-web-research/0.1 AUSI CrossrefAdapter"},
            )
        finally:
            if close_client:
                await client.aclose()

    async def execute(
        self,
        action: AuthorizedAction,
        context: ExecutionContext,
    ) -> ProviderObservation:
        raw = action.action
        if raw.method_ref != VersionRef("method.lexical_search", "1.0.0"):
            raise CrossrefAdapterError(f"unsupported method: {raw.method_ref}")
        if raw.provider_ref != VersionRef(CROSSREF_PROVIDER_ID, CROSSREF_PROVIDER_VERSION):
            raise CrossrefAdapterError(f"wrong provider: {raw.provider_ref}")
        if raw.surface_id != CROSSREF_SURFACE_ID or raw.binding_id != CROSSREF_BINDING_ID:
            raise CrossrefAdapterError("action does not match Crossref binding")

        query = raw.parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise CrossrefAdapterError("Crossref lexical search requires non-empty query")

        top_k_raw = raw.parameters.get("top_k", 5)
        if isinstance(top_k_raw, bool) or not isinstance(top_k_raw, int):
            raise CrossrefAdapterError("top_k must be an integer")
        top_k = max(1, min(top_k_raw, 20))

        params: dict[str, object] = {
            "query.bibliographic": query.strip(),
            "rows": top_k,
            "select": _CROSSREF_SELECT,
        }
        mailto = context.services.get("crossref_mailto")
        if isinstance(mailto, str) and mailto.strip():
            params["mailto"] = mailto.strip()

        filters: list[str] = []
        from_pub_date = raw.parameters.get("from_pub_date")
        until_pub_date = raw.parameters.get("until_pub_date")
        work_type = raw.parameters.get("type")
        if isinstance(from_pub_date, str) and from_pub_date:
            filters.append(f"from-pub-date:{from_pub_date}")
        if isinstance(until_pub_date, str) and until_pub_date:
            filters.append(f"until-pub-date:{until_pub_date}")
        if isinstance(work_type, str) and work_type:
            filters.append(f"type:{work_type}")
        if filters:
            params["filter"] = ",".join(filters)

        response = await self._get(context, params)
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise CrossrefAdapterError(f"Crossref request failed: {exc}") from exc

        if not isinstance(payload, Mapping):
            raise CrossrefAdapterError("Crossref response is not an object")
        message = payload.get("message")
        if not isinstance(message, Mapping):
            raise CrossrefAdapterError("Crossref response missing message")
        items = message.get("items")
        if not isinstance(items, list):
            raise CrossrefAdapterError("Crossref works response missing items")

        artifacts: list[ArtifactRef] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                continue
            doi_value = item.get("DOI")
            doi = str(doi_value).lower() if doi_value else None
            artifact_id = (
                f"crossref:doi:{doi}"
                if doi
                else f"{raw.action_id}:crossref:{index}"
            )
            artifacts.append(
                ArtifactRef(
                    ArtifactKind.CANDIDATE,
                    artifact_id,
                    metadata={
                        "doi": doi,
                        "title": _title(item),
                        "container_title": _container_title(item),
                        "publisher": (
                            str(item.get("publisher"))
                            if item.get("publisher") is not None else None
                        ),
                        "type": (
                            str(item.get("type"))
                            if item.get("type") is not None else None
                        ),
                        "url": (
                            str(item.get("URL"))
                            if item.get("URL") is not None else None
                        ),
                        "published": _published(item),
                        "authors": _authors(item),
                        "source_type": "crossref_metadata",
                        "external_source": True,
                        "provider_rank": index,
                        "score_semantics": "crossref_provider_order",
                    },
                )
            )

        headers = getattr(response, "headers", {}) or {}
        rate_limit = {
            "limit": headers.get("x-rate-limit-limit"),
            "interval": headers.get("x-rate-limit-interval"),
            "concurrency": headers.get("x-concurrency-limit"),
        }
        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:crossref",
            action_id=raw.action_id,
            provider_id=CROSSREF_PROVIDER_ID,
            surface_id=CROSSREF_SURFACE_ID,
            status=ObservationStatus.SUCCEEDED,
            artifacts=tuple(artifacts),
            raw_ref=None,
            result_count=len(artifacts),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=str(
                context.services.get("clock")
                or raw.created_at
            ),
            metadata={
                "query": query.strip(),
                "rate_limit": rate_limit,
                "mailto_used": bool(params.get("mailto")),
                "abstracts_excluded": True,
            },
        )
