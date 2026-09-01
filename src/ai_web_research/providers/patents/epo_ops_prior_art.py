from __future__ import annotations

from xml.etree import ElementTree as ET

from ai_web_research.core.types import ArtifactKind, ArtifactRef, VersionRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind

from .epo_ops import EPO_OPS_BASE_URL, epo_ops_policy_profile


PROVIDER_ID = "provider.epo_ops"
PROVIDER_VERSION = "1.1.0"
SURFACE_ID = "surface.epo_ops.rest"
ADAPTER_ID = "epo.ops.prior_art"
ADAPTER_VERSION = "1.1.0"


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _children(node, name):
    return (child for child in node.iter() if _local(child.tag) == name)


def _text(node, name):
    for child in _children(node, name):
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _date(value):
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) == 8 else value


def _doc_id(ref):
    ids = list(_children(ref, "document-id")) if ref is not None else []
    if not ids:
        return None, None, None, None
    node = next((item for item in ids if item.attrib.get("document-id-type") == "docdb"), ids[0])
    return _text(node, "country"), _text(node, "doc-number"), _text(node, "kind"), _date(_text(node, "date"))


def _publication(country, number, kind):
    return f"{country}{number}{kind or ''}".replace(" ", "").upper() if country and number else None


def _range(value):
    if not isinstance(value, str) or "-" not in value:
        return "1-25"
    try:
        start, end = value.split("-", 1)
        start_i = max(1, int(start))
        end_i = min(100, max(start_i, int(end)))
        return f"{start_i}-{end_i}"
    except Exception:
        return "1-25"


def _search_artifact(doc, index, action_id):
    bibliographic = next(_children(doc, "bibliographic-data"), doc)
    pub_ref = next(_children(bibliographic, "publication-reference"), None)
    app_ref = next(_children(bibliographic, "application-reference"), None)
    country, number, kind, published = _doc_id(pub_ref)
    app_country, app_number, app_kind, _ = _doc_id(app_ref)
    country = country or doc.attrib.get("country")
    number = number or doc.attrib.get("doc-number")
    kind = kind or doc.attrib.get("kind")
    publication = _publication(country, number, kind)
    application = _publication(app_country, app_number, app_kind)

    priorities = []
    for claim in _children(bibliographic, "priority-claim"):
        value = _date(_text(claim, "date"))
        if value and value not in priorities:
            priorities.append(value)

    def classifications(parent_name):
        values = []
        for parent in _children(bibliographic, parent_name):
            for text in _children(parent, "text"):
                if text.text:
                    value = "".join(text.text.split())
                    if value not in values:
                        values.append(value)
        return values

    return ArtifactRef(
        ArtifactKind.CANDIDATE,
        f"epo:publication:{publication}" if publication else f"{action_id}:epo:{index}",
        metadata={
            "publication_number": publication,
            "application_number": application,
            "docdb_publication": f"{country}.{number}.{kind}" if country and number and kind else None,
            "epodoc_publication": f"{country}{number}" if country and number else None,
            "family_id": f"epo:family-id:{doc.attrib.get('family-id')}" if doc.attrib.get("family-id") else None,
            "title": _text(bibliographic, "invention-title"),
            "abstract": None,
            "publication_date": published,
            "priority_dates": priorities,
            "applicants": [],
            "inventors": [],
            "cpc": classifications("classifications-cpc"),
            "ipc": classifications("classifications-ipcr"),
            "source_type": "epo_ops_bibliographic",
            "external_source": True,
            "provider_rank": index,
            "score_semantics": "epo_ops_provider_order",
        },
    )


def _family(root, requested):
    publications = []
    priorities = []
    family_id = None
    for node in root.iter():
        family_id = family_id or node.attrib.get("family-id")
        if _local(node.tag) != "family-member":
            continue
        country, number, kind, _ = _doc_id(next(_children(node, "publication-reference"), None))
        publication = _publication(country, number, kind)
        if publication and publication not in publications:
            publications.append(publication)
        for claim in _children(node, "priority-claim"):
            priority_country, priority_number, _, priority_date = _doc_id(claim)
            if priority_country and priority_number:
                ref = f"{priority_country}{priority_number}" + (f"@{priority_date}" if priority_date else "")
                if ref not in priorities:
                    priorities.append(ref)
    return ArtifactRef(
        ArtifactKind.STRUCTURED_RECORD,
        f"epo:family-id:{family_id}" if family_id else f"epo:family:{requested.replace('.', '')}",
        metadata={
            "family_type": "INPADOC_EXTENDED",
            "provider": "EPO_OPS",
            "definition_version": "ops-family-v3.2",
            "member_publications": publications,
            "priority_refs": priorities,
            "source_type": "epo_ops_family",
            "external_source": True,
        },
    )


def _claims(root, publication):
    language = None
    claims = []
    for node in root.iter():
        if _local(node.tag) == "claims" and language is None:
            language = node.attrib.get("lang")
        if _local(node.tag) != "claim":
            continue
        text = " ".join(part.strip() for part in node.itertext() if part and part.strip())
        if not text:
            continue
        raw_number = node.attrib.get("num") or node.attrib.get("id") or str(len(claims) + 1)
        digits = "".join(ch for ch in raw_number if ch.isdigit())
        claims.append({"claim_number": int(digits or len(claims) + 1), "text": text})
    return ArtifactRef(
        ArtifactKind.DOCUMENT,
        f"epo:claims:{publication}",
        metadata={
            "publication_number": publication,
            "language": language.lower() if language else None,
            "claims": claims,
            "legal_value_class": "official_data",
            "source_type": "epo_ops_fulltext_claims",
            "manifestation_verification_required": True,
        },
    )


def register_epo_ops_prior_art_provider(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    registry.register_provider(ProviderSpec(
        provider_id=PROVIDER_ID,
        version=PROVIDER_VERSION,
        kind=ProviderKind.PATENT,
        display_name="EPO OPS Prior-Art",
        domains=("patent", "patent_intelligence"),
        languages=(),
        jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id=SURFACE_ID,
            kind=SurfaceKind.AUTHENTICATED_API,
            endpoint_ref=EPO_OPS_BASE_URL,
            capabilities=frozenset({
                "capability.lexical",
                "capability.taxonomy_filter",
                "capability.date_filter",
                "capability.patent_family",
                "capability.patent_claims_fulltext",
            }),
            auth_profile="oauth2.epo_ops",
            policy_profile_refs=("policy.epo_ops.rest@1.0.0",),
            static_limits={},
            metadata={"provider_extension": "prior_art_v0.1"},
        ),),
        metadata={},
    ))
    rows = (
        ("binding.lexical_search.epo_ops_prior_art.v1", "method.lexical_search"),
        ("binding.patent_classification.epo_ops_prior_art.v1", "method.patent.classification_search"),
        ("binding.patent_family.epo_ops_prior_art.v1", "method.patent.family_resolve"),
        ("binding.patent_claims.epo_ops_prior_art.v1", "method.patent.claims_fetch"),
    )
    for binding_id, method_id in rows:
        registry.register_binding(MethodBinding(
            binding_id=binding_id,
            method_ref=VersionRef(method_id, "1.0.0"),
            provider_ref=VersionRef(PROVIDER_ID, PROVIDER_VERSION),
            surface_id=SURFACE_ID,
            adapter_id=ADAPTER_ID,
            adapter_version=ADAPTER_VERSION,
            enabled=True,
            parameter_mapping={},
            metadata={},
        ), methods)


class EpoOpsPriorArtAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION

    async def execute(self, action: AuthorizedAction, context: ExecutionContext):
        raw = action.action
        token = context.services.get("epo_ops_access_token")
        client = context.services.get("epo_ops_http_client")
        if not isinstance(token, str) or not token:
            raise RuntimeError("EPO OPS OAuth token required")
        if client is None:
            raise RuntimeError("EPO OPS HTTP client missing")

        params = {}
        accept = "application/xml"
        if raw.method_ref.id == "method.lexical_search":
            query = str(raw.parameters.get("query") or "").strip()
            if not query:
                raise RuntimeError("lexical query required")
            path = "/published-data/search"
            params = {"q": f'ta all "{query}"', "Range": _range(raw.parameters.get("range", "1-25"))}
            parser = "search"
        elif raw.method_ref.id == "method.patent.classification_search":
            scheme = raw.parameters.get("scheme")
            classification = str(raw.parameters.get("classification") or "").strip()
            if scheme not in {"ipc", "cpc"} or not classification:
                raise RuntimeError("valid classification and scheme required")
            path = "/published-data/search"
            params = {"q": f"{scheme}={classification}", "Range": _range(raw.parameters.get("range", "1-25"))}
            parser = "search"
        elif raw.method_ref.id == "method.patent.family_resolve":
            requested = str(raw.parameters.get("docdb_publication") or "").strip()
            if not requested:
                raise RuntimeError("docdb publication required")
            path = f"/family/publication/docdb/{requested}"
            parser = "family"
        elif raw.method_ref.id == "method.patent.claims_fetch":
            requested = str(raw.parameters.get("epodoc_publication") or "").strip()
            if not requested:
                raise RuntimeError("epodoc publication required")
            publication = str(raw.parameters.get("publication_number") or requested)
            path = f"/published-data/publication/epodoc/{requested}/claims"
            parser = "claims"
            accept = "application/fulltext+xml"
        else:
            raise RuntimeError("unsupported EPO OPS prior-art method")

        response = await client.get(
            f"{EPO_OPS_BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": accept},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        if parser == "search":
            artifacts = tuple(
                _search_artifact(doc, index, raw.action_id)
                for index, doc in enumerate((node for node in root.iter() if _local(node.tag) == "exchange-document"), 1)
            )
        elif parser == "family":
            artifacts = (_family(root, requested),)
        else:
            artifacts = (_claims(root, publication),)

        return ProviderObservation(
            observation_id=f"{raw.action_id}:observation:epo_ops_prior_art",
            action_id=raw.action_id,
            provider_id=PROVIDER_ID,
            surface_id=SURFACE_ID,
            status=ObservationStatus.SUCCEEDED,
            artifacts=artifacts,
            raw_ref=None,
            result_count=len(artifacts),
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=str(context.services.get("clock") or raw.created_at),
            metadata={"endpoint_path": path, "credential_profile_id": action.credential_profile_id},
        )


def epo_ops_prior_art_policy_profile():
    return epo_ops_policy_profile()
