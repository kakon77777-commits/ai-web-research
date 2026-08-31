from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.providers.builtin import register_builtin_providers
from ai_web_research.providers.legacy.register import register_legacy_adapters
from ai_web_research.providers.registry import ProviderRegistry


def test_every_enabled_builtin_binding_resolves_an_exact_legacy_adapter():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_builtin_providers(providers, methods.snapshot())
    snapshot = providers.snapshot()

    adapters = AdapterRegistry()
    register_legacy_adapters(adapters)

    for binding in snapshot.bindings:
        if binding.enabled:
            adapter = adapters.get(binding.adapter_id, binding.adapter_version)
            assert adapter.adapter_id == binding.adapter_id
            assert adapter.adapter_version == binding.adapter_version
