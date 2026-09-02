from ai_web_research.project import PROJECT_IDENTITY
from ai_web_research.providers.spec import ProviderKind, ProviderSpec, ProviderTopology
from ai_web_research.providers.builtin import register_builtin_providers
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.providers.registry import ProviderRegistry


def test_project_identity_distinguishes_codename_technical_name_and_legacy_repo():
    assert PROJECT_IDENTITY.codename == "Omphalos"
    assert PROJECT_IDENTITY.technical_name == "AUSI Runtime"
    assert PROJECT_IDENTITY.full_technical_name == "AI-Native Unified Search Intelligence Runtime"
    assert PROJECT_IDENTITY.core_identity == "AI-native Search Method Runtime"
    assert PROJECT_IDENTITY.legacy_repository_name == "ai-web-research"


def test_provider_topology_is_orthogonal_to_provider_kind():
    spec = ProviderSpec(
        provider_id="provider.example",
        version="1.0.0",
        kind=ProviderKind.SEARCH_ENGINE,
        display_name="Example",
        domains=(),
        languages=(),
        jurisdictions=(),
        surfaces=(),
        metadata={},
        topology=ProviderTopology.MODEL_NATIVE,
    )
    assert spec.kind is ProviderKind.SEARCH_ENGINE
    assert spec.topology is ProviderTopology.MODEL_NATIVE


def test_provider_spec_remains_backward_compatible_when_topology_is_omitted():
    spec = ProviderSpec(
        provider_id="provider.old",
        version="1.0.0",
        kind=ProviderKind.CUSTOM,
        display_name="Old",
        domains=(),
        languages=(),
        jurisdictions=(),
        surfaces=(),
        metadata={},
    )
    assert spec.topology is ProviderTopology.UNSPECIFIED


def test_builtin_local_providers_are_marked_local_private():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_builtin_providers(providers, methods.snapshot())
    snapshot = providers.snapshot()
    local = next(provider for provider in snapshot.providers if provider.provider_id == "provider.local_corpus")
    crawler = next(provider for provider in snapshot.providers if provider.provider_id == "provider.crawler")
    assert local.topology is ProviderTopology.LOCAL_PRIVATE
    assert crawler.topology is ProviderTopology.LOCAL_PRIVATE


def test_effective_topology_maps_existing_external_providers_without_rewriting_them():
    from ai_web_research.providers.topology import DEFAULT_PROVIDER_TOPOLOGIES
    assert DEFAULT_PROVIDER_TOPOLOGIES["provider.brave_search"] is ProviderTopology.PROVIDER_NEUTRAL
    assert DEFAULT_PROVIDER_TOPOLOGIES["provider.crossref"] is ProviderTopology.DOMAIN_SPECIFIC
    assert DEFAULT_PROVIDER_TOPOLOGIES["provider.epo_ops"] is ProviderTopology.DOMAIN_SPECIFIC
