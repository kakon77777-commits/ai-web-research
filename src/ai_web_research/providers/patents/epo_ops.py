from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Iterable
from xml.etree import ElementTree as ET

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


EPO_OPS_PROVIDER_ID = "provider.epo_ops"
EPO_OPS_PROVIDER_VERSION = "1.0.0"
EPO_OPS_SURFACE_ID = "surface.epo_ops.rest"
EPO_OPS_ADAPTER_ID = "epo.ops"
EPO_OPS_ADAPTER_VERSION = "1.0.0"
EPO_OPS_BASE_URL = "https://ops.epo.org/3.2/rest-services"


class EpoOpsAdapterError(RuntimeError):
    pass


class EpoOpsAuthError(EpoOpsAdapterError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(node: ET.Element, name: str) -> Iterable[ET.Element]:
    for child in node.iter():
        if _local(child.tag) == name:
            yield child


def _first_text(node: ET.Element, name: str) -> str | None:
    for child in _children(node, name):
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _format_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return raw


def _doc_id(ref: ET.Element | None) -> tuple[str | None, str | None, str | None, str | None]:
    if ref is None:
        return None, None, None, None
    ids = [x for x in _children(ref, "document-id")]
    if not ids:
        return None, None, None, None
    preferred = next((x for x in ids if x.attrib.get("document-id-type") == "docdb"), ids[0])
    country = _first_text(preferred, "country")
    number = _first_text(preferred, "doc-number")
    kind = _first_text(preferred, "kind")
    date = _first_text(preferred, "date")
    return country, number, kind, _format_date(date)


def _normalize_publication(country: str | None, number: str | None, kind: str | None) -> str | None:
    if not country or not number:
        return None
    return f"{country}{number}{kind or ''}".replace(" ", "").upper()


def _party_names(doc: ET.Element, role: str) -> list[str]:
    names: list[str] = []
    for node in _children(doc, role):
        for name in _children(node, "name"):
            if name.text and name.text.strip():
                value = name.text.strip()
                if value not in names:
                    names.append(value)
    return names


def _classifications(doc: ET.Element, parent_name: str) -> list[str]:
    values: list[str] = []
    for parent in _children(doc, parent_name):
        for text in _children(parent, "text"):
            if text.text and text.text.strip():
                value = "".join(text.text.split())
                if value not in values:
                    values.append(value)
    return values


def _priority_dates(doc: ET.Element) -> list[str]:
    values: list[str] = []
    for claim in _children(doc, "priority-claim"):
        date = _first_text(claim, "date")
        formatted = _format_date(date)
        if formatted and formatted not in values:
            values.append(formatted)
    return values


def _parse_exchange_document(doc: ET.Element, index: int, action_id: str) -> ArtifactRef:
    bibliographic = next(_children(doc, "bibliographic-data"), doc)
    pub_ref = next(_children(bibliographic, "publication-reference"), None)
    app_ref = next(_children(bibliographic, "application-reference"), None)

    pub_country, pub_number, pub_kind, pub_date = _doc_id(pub_ref)
    app_country, app_number, app_kind, _ = _doc_id(app_ref)

    pub_country = pub_country or doc.attrib.get("country")
    pub_number = pub_number or doc.attrib.get("doc-number")
    pub_kind = pub_kind or doc.attrib.get("kind")

    publication = _normalize_publication(pub_country, pub_number, pub_kind)
    application = _normalize_publication(app_country, app_number, app_kind)
    title = _first_text(bibliographic, "invention-title")

    cpc = _classifications(bibliographic, "classifications-cpc")
    ipc = _classifications(bibliographic, "classifications-ipcr")
    priorities = _priority_dates(bibliographic)
    applicants = _party_names(bibliographic, "applicants")
    inventors = _party_names(bibliographic, "inventors")

    artifact_id = f"epo:publication:{publication}" if publication else f"{action_id}:epo:{index}"
    return ArtifactRef(
        ArtifactKind.CANDIDATE,
        artifact_id,
        metadata={
            "publication_number": publication,
            "application_number": application,
            "title": title,
            "publication_date": pub_date,
            "priority_dates": priorities,
            "applicants": applicants,
            "inventors": inventors,
            "cpc": cpc,
            "ipc": ipc,
            "source_type": "epo_ops_bibliographic",
            "external_source": True,
            "provider_rank": index,
            "score_semantics": "epo_ops_provider_order",
        },
    )


def _range(value: object) -> str:
    if not isinstance(value, str) or "-" not in value:
        return "1-25"
    try:
        start_s, end_s = value.split("-", 1)
        start = max(1, int(start_s))
        end = max(start, int(end_s))
    except Exception:
        return "1-25"
    end = min(end, 100)
    return f"{start}-{end}"


def _policy_hash(rules: tuple[PolicyRule, ...]) -> str:
    payload = [{"id": r.rule_id, "action": r.action.value, "effect": r.effect.value, "value": r.value, "constraints": r.constraints} for r in rules]
    return sha256(dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def epo_ops_policy_profile() -> SourcePolicyProfile:
    terms = PolicySourceRef(
        source_id="policy-source.epo.ops.terms",
        uri="https://www.epo.org/en/service-support/ordering/terms-and-conditions/ops-terms-and-conditions",
        title="Terms and conditions for use of the EPO's Open Patent Services (OPS)",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at=None, expires_at=None, content_hash=None,
        anchor={"sections": ["3 Use of the data", "4 Payments due"]},
        authority="provider", interpretation_status="provider_human_readable",
    )
    fair = PolicySourceRef(
        source_id="policy-source.epo.ops.fair-use",
        uri="https://www.epo.org/en/service-support/ordering/fair-use",
        title="Fair use charter for the EPO's online patent information products",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at=None, expires_at=None, content_hash=None,
        anchor={"section": "Automated queries"},
        authority="provider", interpretation_status="provider_human_readable",
    )
    ops = PolicySourceRef(
        source_id="policy-source.epo.ops.service",
        uri="https://www.epo.org/en/searching-for-patents/data/web-services/ops",
        title="Open Patent Services (OPS)",
        retrieved_at="2026-08-31T12:00:00+00:00",
        effective_at=None, expires_at=None, content_hash=None,
        anchor={"section": "Getting started / Conditions"},
        authority="provider", interpretation_status="provider_human_readable",
    )

    allowed = (
        AcquisitionAction.AUTOMATED_QUERY,
        AcquisitionAction.PERSISTENT_CACHE,
        AcquisitionAction.INDEX,
        AcquisitionAction.INTERNAL_USE,
        AcquisitionAction.COMMERCIAL_USE,
        AcquisitionAction.DISTRIBUTE_DERIVED,
        AcquisitionAction.LINK,
    )
    rules: list[PolicyRule] = []
    for action in allowed:
        rules.append(PolicyRule(
            rule_id=f"epo-ops-allow-{action.value}", action=action,
            effect=PolicyRuleEffect.PERMISSION, value=True,
            asset_scope="ops_data", party_scope=None, purpose_scope=(), constraints={},
            source_refs=("policy-source.epo.ops.terms",), priority_hint=10,
        ))
    rules.append(PolicyRule(
        rule_id="epo-ops-deny-raw-redistribution",
        action=AcquisitionAction.REDISTRIBUTE_RAW,
        effect=PolicyRuleEffect.PROHIBITION, value=True,
        asset_scope="ops_data_as_such", party_scope=None, purpose_scope=(), constraints={},
        source_refs=("policy-source.epo.ops.terms",), priority_hint=100,
    ))
    rules.extend((
        PolicyRule(
            rule_id="epo-ops-family-rate", action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT, value=1,
            asset_scope="family_related_actions", party_scope=None, purpose_scope=(),
            constraints={"unit": "requests", "window": "second"},
            source_refs=("policy-source.epo.ops.fair-use",), priority_hint=20,
        ),
        PolicyRule(
            rule_id="epo-ops-search-rate", action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT, value=10,
            asset_scope="search_actions", party_scope=None, purpose_scope=(),
            constraints={"unit": "searches", "window": "minute_per_ip"},
            source_refs=("policy-source.epo.ops.fair-use",), priority_hint=20,
        ),
        PolicyRule(
            rule_id="epo-ops-traffic-volume", action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT, value=1,
            asset_scope="automated_traffic", party_scope=None, purpose_scope=(),
            constraints={"unit": "Mbit", "window": "second"},
            source_refs=("policy-source.epo.ops.fair-use",), priority_hint=20,
        ),
        PolicyRule(
            rule_id="epo-ops-free-weekly-volume", action=AcquisitionAction.AUTOMATED_QUERY,
            effect=PolicyRuleEffect.CONSTRAINT, value=4,
            asset_scope="non_paying_user", party_scope=None, purpose_scope=(),
            constraints={"unit": "GB", "window": "calendar_week_gmt"},
            source_refs=("policy-source.epo.ops.service",), priority_hint=20,
        ),
    ))
    tuple_rules = tuple(rules)
    return SourcePolicyProfile(
        policy_id="policy.epo_ops.rest", version="1.0.0",
        provider_id=EPO_OPS_PROVIDER_ID, surface_id=EPO_OPS_SURFACE_ID,
        asset_scope="ops_data", rules=tuple_rules, policy_sources=(terms, fair, ops),
        auth_requirements={"oauth2": True, "registration_required": True, "credential_profile": "oauth2.epo_ops"},
        rate_limits={"family_requests_per_second": 1, "search_actions_per_minute_per_ip": 10, "max_traffic_mbit_per_second": 1, "free_gb_per_week": 4},
        retention_rules={}, attribution_rules={},
        redistribution_rules={"raw_data_public_redistribution": "prohibited", "data_as_part_of_products": "permitted_under_ops_terms"},
        privacy_flags=(), observed_at="2026-08-31T12:00:00+00:00",
        effective_at=None, expires_at=None, next_review_at="2026-09-30T00:00:00+00:00",
        policy_hash=_policy_hash(tuple_rules), review_status="provider_documented",
        metadata={"bulk_note": "Use EPO raw/bulk products for complete databases or very large datasets.", "rest_bulk_retrieval_limit_documents": 100},
    )


def register_epo_ops_policy(registry) -> None:
    registry.register(epo_ops_policy_profile())


def register_epo_ops_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    provider = ProviderSpec(
        provider_id=EPO_OPS_PROVIDER_ID, version=EPO_OPS_PROVIDER_VERSION,
        kind=ProviderKind.PATENT, display_name="EPO Open Patent Services",
        domains=("patent", "patent_intelligence"), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id=EPO_OPS_SURFACE_ID, kind=SurfaceKind.AUTHENTICATED_API,
            endpoint_ref=EPO_OPS_BASE_URL,
            capabilities=frozenset({"capability.lexical", "capability.taxonomy_filter", "capability.date_filter"}),
            auth_profile="oauth2.epo_ops", policy_profile_refs=("policy.epo_ops.rest@1.0.0",),
            static_limits={"search_actions_per_minute_per_ip": 10, "family_requests_per_second": 1, "free_gb_per_week": 4},
            metadata={"structured_format": "xml", "oauth2": True},
        ),), metadata={"official_source": True},
    )
    registry.register_provider(provider)
    for binding in (
        MethodBinding(
            binding_id="binding.lexical_search.epo_ops.v1",
            method_ref=VersionRef("method.lexical_search", "1.0.0"),
            provider_ref=VersionRef(EPO_OPS_PROVIDER_ID, EPO_OPS_PROVIDER_VERSION),
            surface_id=EPO_OPS_SURFACE_ID, adapter_id=EPO_OPS_ADAPTER_ID,
            adapter_version=EPO_OPS_ADAPTER_VERSION, enabled=True, parameter_mapping={},
            metadata={"endpoint": "/published-data/search"},
        ),
        MethodBinding(
            binding_id="binding.patent_classification.epo_ops.v1",
            method_ref=VersionRef("method.patent.classification_search", "1.0.0"),
            provider_ref=VersionRef(EPO_OPS_PROVIDER_ID, EPO_OPS_PROVIDER_VERSION),
            surface_id=EPO_OPS_SURFACE_ID, adapter_id=EPO_OPS_ADAPTER_ID,
            adapter_version=EPO_OPS_ADAPTER_VERSION, enabled=True, parameter_mapping={},
            metadata={"endpoint": "/published-data/search"},
        ),
    ):
        registry.register_binding(binding, methods)


def register_epo_ops_adapter(registry) -> None:
    registry.register(EpoOpsAdapter())


class EpoOpsAdapter:
    adapter_id = EPO_OPS_ADAPTER_ID
    adapter_version = EPO_OPS_ADAPTER_VERSION

    async def _get(self, context: ExecutionContext, params: dict[str, object], token: str):
        client = context.services.get("epo_ops_http_client")
        close_client = False
        if client is None:
            import httpx
            client = httpx.AsyncClient(timeout=30.0)
            close_client = True
        try:
            return await client.get(
                f"{EPO_OPS_BASE_URL}/published-data/search", params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/xml", "User-Agent": "ai-web-research/0.1 AUSI EPO-OPS"},
            )
        finally:
            if close_client:
                await client.aclose()

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw = action.action
        if raw.provider_ref != VersionRef(EPO_OPS_PROVIDER_ID, EPO_OPS_PROVIDER_VERSION):
            raise EpoOpsAdapterError(f"wrong provider: {raw.provider_ref}")
        if raw.surface_id != EPO_OPS_SURFACE_ID:
            raise EpoOpsAdapterError(f"wrong surface: {raw.surface_id}")
        if raw.binding_id not in {"binding.lexical_search.epo_ops.v1", "binding.patent_classification.epo_ops.v1"}:
            raise EpoOpsAdapterError("unsupported EPO OPS binding")

        token = context.services.get("epo_ops_access_token")
        if not isinstance(token, str) or not token.strip():
            raise EpoOpsAuthError("EPO OPS requires an OAuth 2.0 access token")

        if raw.method_ref == VersionRef("method.lexical_search", "1.0.0"):
            query = raw.parameters.get("query")
            if not isinstance(query, str) or not query.strip():
                raise EpoOpsAdapterError("lexical search requires non-empty query")
            cql = f'ta all "{query.strip()}"'
        elif raw.method_ref == VersionRef("method.patent.classification_search", "1.0.0"):
            symbol = raw.parameters.get("classification")
            scheme = raw.parameters.get("scheme")
            if not isinstance(symbol, str) or not symbol.strip():
                raise EpoOpsAdapterError("classification search requires symbol")
            if scheme not in {"ipc", "cpc"}:
                raise EpoOpsAdapterError("classification scheme must be ipc or cpc")
            cql = f"{scheme}={symbol.strip()}"
        else:
            raise EpoOpsAdapterError(f"unsupported method: {raw.method_ref}")

        params = {"q": cql, "Range": _range(raw.parameters.get("range", "1-25"))}
        response = await self._get(context, params, token.strip())
        try:
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:
            raise EpoOpsAdapterError(f"EPO OPS request/parse failed: {exc}") from exc

        docs = [node for node in root.iter() if _local(node.tag) == "exchange-document"]
        artifacts = tuple(_parse_exchange_document(doc, index, raw.action_id) for index, doc in enumerate(docs, start=1))
        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:epo_ops", action_id=raw.action_id,
            provider_id=EPO_OPS_PROVIDER_ID, surface_id=EPO_OPS_SURFACE_ID,
            status=ObservationStatus.SUCCEEDED, artifacts=artifacts, raw_ref=None,
            result_count=len(artifacts), cost={}, latency_ms=None, continuation={}, diagnostics=(),
            occurred_at=str(context.services.get("clock") or raw.created_at),
            metadata={"cql": cql, "range": params["Range"], "quota_headers": dict(getattr(response, "headers", {}) or {}), "credential_profile_id": action.credential_profile_id},
        )
