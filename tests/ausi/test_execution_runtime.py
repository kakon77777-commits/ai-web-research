from dataclasses import replace

import pytest

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    SearchAction,
    VersionRef,
)
from ai_web_research.execution.models import (
    AuthorizationResult,
    AuthorizedAction,
    ExecutionContext,
    ObservationStatus,
    PolicyDecision,
    ProviderObservation,
)
from ai_web_research.execution.registry import AdapterNotFound, AdapterRegistry, AdapterVersionConflict
from ai_web_research.execution.runtime import ExecutionRejected, ExecutionRuntime
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.providers.builtin import register_builtin_providers
from ai_web_research.providers.registry import ProviderRegistry


class FakeAdapter:
    def __init__(self, marker: str = "ok") -> None:
        self.marker = marker
        self.calls = 0

    @property
    def adapter_id(self) -> str:
        return "legacy.identity_search"

    @property
    def adapter_version(self) -> str:
        return "legacy-ca57faf6"

    async def execute(self, action, context):
        self.calls += 1
        return ProviderObservation(
            observation_id="obs-1",
            action_id=action.action.action_id,
            provider_id=action.action.provider_ref.id,
            surface_id=action.action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(ArtifactRef(ArtifactKind.CANDIDATE, "doc-1", metadata={"marker": self.marker}),),
            raw_ref=None,
            result_count=1,
            cost={},
            latency_ms=0.1,
            continuation={},
            diagnostics=(),
            occurred_at="2026-08-31T09:00:01+00:00",
            metadata={},
        )


def provider_snapshot():
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_builtin_providers(providers, methods.snapshot())
    return providers.snapshot()


def make_action(binding_id="binding.identity_search.local_corpus.v1"):
    return SearchAction(
        action_id="a1",
        task_id="t1",
        epoch_id="e1",
        method_ref=VersionRef("method.identity_search", "1.0.0"),
        provider_ref=VersionRef("provider.local_corpus", "1.0.0"),
        surface_id="surface.local.sqlite",
        binding_id=binding_id,
        action_kind=ActionKind.RESOLVE_IDENTITY,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"query": "alpha"},
        guards=(),
        expected_effects=(),
        created_by="test",
        created_at="2026-08-31T09:00:00+00:00",
    )


def test_adapter_registry_resolves_exact_version_only():
    registry = AdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    assert registry.get("legacy.identity_search", "legacy-ca57faf6") is adapter
    with pytest.raises(AdapterNotFound):
        registry.get("legacy.identity_search", "other")


def test_adapter_registry_rejects_conflicting_same_version_registration():
    registry = AdapterRegistry()
    registry.register(FakeAdapter("one"))
    with pytest.raises(AdapterVersionConflict):
        registry.register(FakeAdapter("two"))


@pytest.mark.asyncio
async def test_execution_runtime_rejects_non_allowed_action_before_adapter_call():
    adapter_registry = AdapterRegistry()
    adapter = FakeAdapter()
    adapter_registry.register(adapter)
    runtime = ExecutionRuntime(adapter_registry, provider_snapshot())
    wrapped = AuthorizedAction(make_action(), AuthorizationResult(PolicyDecision.DENY))
    with pytest.raises(ExecutionRejected, match="not executable"):
        await runtime.execute(wrapped, ExecutionContext("t1", "e1", "snap"))
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_execution_runtime_resolves_binding_and_executes_adapter():
    adapter_registry = AdapterRegistry()
    adapter = FakeAdapter()
    adapter_registry.register(adapter)
    runtime = ExecutionRuntime(adapter_registry, provider_snapshot())
    wrapped = AuthorizedAction(make_action(), AuthorizationResult(PolicyDecision.ALLOW))
    obs = await runtime.execute(wrapped, ExecutionContext("t1", "e1", "snap"))
    assert adapter.calls == 1
    assert obs.status is ObservationStatus.SUCCEEDED
    assert obs.artifacts[0].id == "doc-1"


@pytest.mark.asyncio
async def test_execution_runtime_rejects_action_that_disagrees_with_binding():
    adapter_registry = AdapterRegistry()
    adapter_registry.register(FakeAdapter())
    runtime = ExecutionRuntime(adapter_registry, provider_snapshot())
    bad = replace(make_action(), surface_id="surface.wrong")
    with pytest.raises(ExecutionRejected, match="does not match binding"):
        await runtime.execute(
            AuthorizedAction(bad, AuthorizationResult(PolicyDecision.ALLOW)),
            ExecutionContext("t1", "e1", "snap"),
        )
