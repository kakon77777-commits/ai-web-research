from __future__ import annotations

from types import MappingProxyType

from .spec import ProviderSpec, ProviderTopology


_DEFAULT_TOPOLOGIES = {
    "provider.brave_search": ProviderTopology.PROVIDER_NEUTRAL,
    "provider.crossref": ProviderTopology.DOMAIN_SPECIFIC,
    "provider.epo_ops": ProviderTopology.DOMAIN_SPECIFIC,
    "provider.local_corpus": ProviderTopology.LOCAL_PRIVATE,
    "provider.crawler": ProviderTopology.LOCAL_PRIVATE,
}

DEFAULT_PROVIDER_TOPOLOGIES = MappingProxyType(_DEFAULT_TOPOLOGIES)


def effective_provider_topology(provider: ProviderSpec) -> ProviderTopology:
    """Return explicit topology first, then the canonical Omphalos built-in mapping."""
    if provider.topology is not ProviderTopology.UNSPECIFIED:
        return provider.topology
    return DEFAULT_PROVIDER_TOPOLOGIES.get(
        provider.provider_id,
        ProviderTopology.UNSPECIFIED,
    )
