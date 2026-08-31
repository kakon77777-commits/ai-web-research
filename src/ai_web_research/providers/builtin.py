from __future__ import annotations

from ai_web_research.core.types import VersionRef
from ai_web_research.methods.registry import MethodRegistrySnapshot
from .registry import ProviderRegistry
from .spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind


def register_builtin_providers(registry: ProviderRegistry, methods: MethodRegistrySnapshot) -> None:
    local = ProviderSpec(
        provider_id="provider.local_corpus", version="1.0.0", kind=ProviderKind.LOCAL_CORPUS,
        display_name="Local corpus", domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id="surface.local.sqlite", kind=SurfaceKind.LOCAL_DATABASE, endpoint_ref=None,
            capabilities=frozenset({"capability.lexical", "capability.identity_fold"}),
            auth_profile=None, policy_profile_refs=(), static_limits={}, metadata={},
        ),), metadata={},
    )
    crawler = ProviderSpec(
        provider_id="provider.crawler", version="1.0.0", kind=ProviderKind.CRAWLER,
        display_name="Legacy crawler", domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id="surface.crawler.browser", kind=SurfaceKind.PUBLIC_API, endpoint_ref=None,
            capabilities=frozenset({"capability.fetch_url", "capability.crawl_links"}),
            auth_profile=None, policy_profile_refs=(), static_limits={}, metadata={},
        ),), metadata={},
    )
    llm = ProviderSpec(
        provider_id="provider.llm_recall", version="1.0.0", kind=ProviderKind.LLM_RECALL,
        display_name="Legacy LLM recall", domains=(), languages=(), jurisdictions=(),
        surfaces=(ProviderSurface(
            surface_id="surface.llm.vertex", kind=SurfaceKind.MODEL, endpoint_ref=None,
            capabilities=frozenset({"capability.llm_generate", "capability.extract_structured"}),
            auth_profile=None, policy_profile_refs=(), static_limits={}, metadata={},
        ),), metadata={},
    )
    for provider in (local, crawler, llm):
        registry.register_provider(provider)

    binding_rows = (
        ("binding.identity_search.local_corpus.v1", "method.identity_search", "provider.local_corpus", "surface.local.sqlite", "legacy.identity_search"),
        ("binding.lexical_search.local_corpus.v1", "method.lexical_search", "provider.local_corpus", "surface.local.sqlite", "legacy.lexical_search"),
        ("binding.query_divergence.llm.v1", "method.query_divergence", "provider.llm_recall", "surface.llm.vertex", "legacy.diverge"),
        ("binding.llm_recall.llm.v1", "method.llm_recall", "provider.llm_recall", "surface.llm.vertex", "legacy.basic_ai_search"),
        ("binding.crawl_discovery.crawler.v1", "method.crawl_discovery", "provider.crawler", "surface.crawler.browser", "legacy.crawl_site"),
        ("binding.fetch_document.crawler.v1", "method.fetch_document", "provider.crawler", "surface.crawler.browser", "legacy.fetch_document"),
        ("binding.extract_candidate_evidence.llm.v1", "method.extract_candidate_evidence", "provider.llm_recall", "surface.llm.vertex", "legacy.semantic_extract"),
    )
    provider_versions = {
        "provider.local_corpus": "1.0.0",
        "provider.crawler": "1.0.0",
        "provider.llm_recall": "1.0.0",
    }
    for binding_id, method_id, provider_id, surface_id, adapter_id in binding_rows:
        registry.register_binding(
            MethodBinding(
                binding_id=binding_id,
                method_ref=VersionRef(method_id, "1.0.0"),
                provider_ref=VersionRef(provider_id, provider_versions[provider_id]),
                surface_id=surface_id,
                adapter_id=adapter_id,
                adapter_version="legacy-ca57faf6",
                enabled=True,
                parameter_mapping={},
                metadata={},
            ),
            methods,
        )
