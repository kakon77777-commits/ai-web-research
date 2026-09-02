from __future__ import annotations

from dataclasses import dataclass

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, VersionRef
from ai_web_research.execution.models import ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.execution.trusted import TrustedExecutionRejected
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.trace import TraceAction, TraceActionKind
from ai_web_research.source_graph.trace_execution import (
    LEXICAL_METHOD,
    TraceExecutionStatus,
    compile_trace_search_action,
    execute_trace_search_action,
    select_lexical_binding,
)


def _registry():
    provider = ProviderSpec(
        "provider.fake",
        "1.0.0",
        ProviderKind.SEARCH_ENGINE,
        "Fake",
        (),
        (),
        (),
        (
            ProviderSurface(
                "surface.fake",
                SurfaceKind.AUTHENTICATED_API,
                None,
                frozenset({"capability.lexical"}),
                None,
                (),
                {},
                {},
            ),
        ),
        {},
    )
    binding = MethodBinding(
        "binding.fake",
        LEXICAL_METHOD,
        VersionRef("provider.fake", "1.0.0"),
        "surface.fake",
        "adapter.fake",
        "1.0.0",
        True,
        {},
        {},
    )
    return ProviderRegistrySnapshot("snap", (provider,), (binding,))


def _compiled():
    binding = select_lexical_binding(_registry())
    trace = TraceAction(
        "trace:1",
        TraceActionKind.EXACT_QUOTE_SEARCH,
        '"rare phrase"',
        None,
        "quoted_phrase",
    )
    return compile_trace_search_action(
        source_id="source:x",
        trace=trace,
        binding=binding,
        task_id="task:1",
        epoch_id="epoch:1",
        created_at="2026-09-01T00:00:00Z",
    )


def _context():
    return ExecutionContext("task:1", "epoch:1", "snap", services={})


def _policy():
    return PolicyContext(
        "task:1",
        "research",
        None,
        RiskClass.LOW,
        (),
        (AcquisitionAction.AUTOMATED_QUERY,),
        "2026-09-01T00:00:00Z",
    )


@dataclass
class Result:
    observation: ProviderObservation


class SuccessRuntime:
    def __init__(self):
        self.calls = []

    async def execute(self, action, context, policy_context, **kwargs):
        self.calls.append((action, context, policy_context, kwargs))
        observation = ProviderObservation(
            observation_id="obs:1",
            action_id=action.action_id,
            provider_id="provider.fake",
            surface_id="surface.fake",
            status=ObservationStatus.SUCCEEDED,
            artifacts=(
                ArtifactRef(
                    ArtifactKind.CANDIDATE,
                    "candidate:1",
                    metadata={
                        "url": "https://official.example/model-x",
                        "provider_rank": 1,
                        "evidence_role": "discovery_only",
                    },
                ),
            ),
            raw_ref=None,
            result_count=1,
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at="2026-09-01T00:00:01Z",
            metadata={"evidence_role": "discovery_only"},
        )
        return Result(observation)


class RejectRuntime:
    async def execute(self, *args, **kwargs):
        exc = TrustedExecutionRejected.__new__(TrustedExecutionRejected)
        RuntimeError.__init__(exc, "rejected")
        raise exc


class FailRuntime:
    async def execute(self, *args, **kwargs):
        raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_success_executes_through_trusted_runtime_and_normalizes_candidates():
    runtime = SuccessRuntime()
    compiled = _compiled()
    result = await execute_trace_search_action(
        compiled,
        trusted_runtime=runtime,
        execution_context=_context(),
        policy_context=_policy(),
    )
    assert result.status is TraceExecutionStatus.SUCCEEDED
    assert result.provider_id == "provider.fake"
    assert result.binding_id == "binding.fake"
    assert result.observation_id == "obs:1"
    assert result.discovery_batch.candidates[0].url == "https://official.example/model-x"
    assert result.discovery_batch.candidates[0].metadata["evidence_role"] == "discovery_only"
    assert runtime.calls[0][0] == compiled.search_action
    assert runtime.calls[0][2] == _policy()


@pytest.mark.asyncio
async def test_policy_rejection_is_typed_when_not_fail_fast():
    result = await execute_trace_search_action(
        _compiled(),
        trusted_runtime=RejectRuntime(),
        execution_context=_context(),
        policy_context=_policy(),
        fail_fast=False,
    )
    assert result.status is TraceExecutionStatus.POLICY_REJECTED
    assert result.discovery_batch is None


@pytest.mark.asyncio
async def test_provider_failure_is_typed_when_not_fail_fast():
    result = await execute_trace_search_action(
        _compiled(),
        trusted_runtime=FailRuntime(),
        execution_context=_context(),
        policy_context=_policy(),
        fail_fast=False,
    )
    assert result.status is TraceExecutionStatus.PROVIDER_FAILED
    assert result.error_code == "RuntimeError"
