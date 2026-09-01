from __future__ import annotations

import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, VersionRef
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.trace import TraceAction, TraceActionKind
from ai_web_research.source_graph.trace_execution import (
    TraceActionNotSearchable,
    TraceExecutionUnavailable,
    compile_trace_search_action,
    select_lexical_binding,
)

LEX = VersionRef("method.lexical_search", "1.0.0")


def _snapshot() -> ProviderRegistrySnapshot:
    providers = []
    bindings = []
    for provider_id, binding_id in (
        ("provider.alpha", "binding.alpha"),
        ("provider.brave_search", "binding.brave"),
    ):
        surface_id = f"surface.{provider_id.split('.')[-1]}"
        providers.append(
            ProviderSpec(
                provider_id=provider_id,
                version="1.0.0",
                kind=ProviderKind.SEARCH_ENGINE,
                display_name=provider_id,
                domains=(),
                languages=(),
                jurisdictions=(),
                surfaces=(
                    ProviderSurface(
                        surface_id=surface_id,
                        kind=SurfaceKind.AUTHENTICATED_API,
                        endpoint_ref=None,
                        capabilities=frozenset({"capability.lexical"}),
                        auth_profile=None,
                        policy_profile_refs=(),
                        static_limits={},
                        metadata={},
                    ),
                ),
                metadata={},
            )
        )
        bindings.append(
            MethodBinding(
                binding_id=binding_id,
                method_ref=LEX,
                provider_ref=VersionRef(provider_id, "1.0.0"),
                surface_id=surface_id,
                adapter_id="adapter",
                adapter_version="1.0.0",
                enabled=True,
                parameter_mapping={},
                metadata={},
            )
        )
    return ProviderRegistrySnapshot("snap", tuple(providers), tuple(bindings))


def _trace(kind: TraceActionKind, query: str | None) -> TraceAction:
    return TraceAction("trace:1", kind, query, None, "fixture")


def test_quote_and_entity_compile_to_existing_lexical_method():
    binding = select_lexical_binding(_snapshot(), provider_preferences=("provider.brave_search",))
    quote = compile_trace_search_action(
        source_id="source:x",
        trace=_trace(TraceActionKind.EXACT_QUOTE_SEARCH, '"rare phrase"'),
        binding=binding,
        task_id="task:1",
        epoch_id="epoch:1",
        created_at="2026-09-01T00:00:00Z",
        top_k=7,
    )
    assert quote.search_action.method_ref == LEX
    assert quote.search_action.action_kind is ActionKind.SEARCH
    assert quote.search_action.parameters == {"query": '"rare phrase"', "top_k": 7}
    assert quote.search_action.inputs[0].kind is ArtifactKind.QUERY
    entity = compile_trace_search_action(
        source_id="source:x",
        trace=_trace(TraceActionKind.ENTITY_SEARCH, '"Official Lab" Model X'),
        binding=binding,
        task_id="task:1",
        epoch_id="epoch:1",
        created_at="2026-09-01T00:00:00Z",
    )
    assert entity.search_action.method_ref == LEX


def test_direct_predecessor_is_not_lexical_search():
    binding = select_lexical_binding(_snapshot())
    with pytest.raises(TraceActionNotSearchable):
        compile_trace_search_action(
            source_id="source:x",
            trace=_trace(TraceActionKind.DIRECT_PREDECESSOR, None),
            binding=binding,
            task_id="task:1",
            epoch_id="epoch:1",
            created_at="2026-09-01T00:00:00Z",
        )


def test_binding_selection_honors_provider_preference_then_is_deterministic():
    snapshot = _snapshot()
    assert select_lexical_binding(
        snapshot,
        provider_preferences=("provider.brave_search",),
    ).provider_ref.id == "provider.brave_search"
    assert select_lexical_binding(snapshot).provider_ref.id == "provider.alpha"


def test_disabled_bindings_are_not_selected():
    snapshot = _snapshot()
    disabled = tuple(
        MethodBinding(
            binding_id=binding.binding_id,
            method_ref=binding.method_ref,
            provider_ref=binding.provider_ref,
            surface_id=binding.surface_id,
            adapter_id=binding.adapter_id,
            adapter_version=binding.adapter_version,
            enabled=False,
            parameter_mapping=binding.parameter_mapping,
            metadata=binding.metadata,
        )
        for binding in snapshot.bindings
    )
    with pytest.raises(TraceExecutionUnavailable):
        select_lexical_binding(ProviderRegistrySnapshot("disabled", snapshot.providers, disabled))
