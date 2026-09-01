from __future__ import annotations

from dataclasses import dataclass

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, VersionRef
from ai_web_research.execution.models import ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.trace import ReverseTracePlan, TraceAction, TraceActionKind
from ai_web_research.source_graph.trace_execution import (
    LEXICAL_METHOD,
    TraceExecutionStatus,
    execute_reverse_trace_plan,
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


def _plan():
    return ReverseTracePlan(
        "source:x",
        (
            TraceAction(
                "trace:direct",
                TraceActionKind.DIRECT_PREDECESSOR,
                None,
                "https://official.example/direct",
                "explicit_attributed_url",
            ),
            TraceAction(
                "trace:quote",
                TraceActionKind.EXACT_QUOTE_SEARCH,
                '"rare phrase"',
                None,
                "quoted_phrase",
            ),
            TraceAction(
                "trace:entity",
                TraceActionKind.ENTITY_SEARCH,
                '"Official Lab" Model X',
                None,
                "attribution_entity",
            ),
        ),
        False,
        None,
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


class Runtime:
    def __init__(self, fail_query=None):
        self.fail_query = fail_query

    async def execute(self, action, context, policy_context, **kwargs):
        query = action.parameters["query"]
        if query == self.fail_query:
            raise RuntimeError("branch failed")
        suffix = "quote" if "rare phrase" in query else "entity"
        observation = ProviderObservation(
            f"obs:{suffix}",
            action.action_id,
            "provider.fake",
            "surface.fake",
            ObservationStatus.SUCCEEDED,
            (
                ArtifactRef(
                    ArtifactKind.CANDIDATE,
                    f"candidate:{suffix}",
                    metadata={
                        "url": f"https://candidate.example/{suffix}",
                        "provider_rank": 1,
                        "evidence_role": "discovery_only",
                    },
                ),
            ),
            None,
            1,
            {},
            None,
            {},
            (),
            "2026-09-01T00:00:01Z",
            {"query": query, "evidence_role": "discovery_only"},
        )
        return Result(observation)


@pytest.mark.asyncio
async def test_plan_skips_direct_predecessor_and_executes_searchable_branches():
    batch = await execute_reverse_trace_plan(
        _plan(),
        providers=_registry(),
        trusted_runtime=Runtime(),
        execution_context=_context(),
        policy_context=_policy(),
        task_id="task:1",
        epoch_id="epoch:1",
        created_at="2026-09-01T00:00:00Z",
    )
    assert batch.skipped_action_ids == ("trace:direct",)
    assert [execution.trace_action_id for execution in batch.executions] == [
        "trace:quote",
        "trace:entity",
    ]
    assert batch.complete is True
    assert batch.failure_count == 0
    assert batch.candidate_count == 2


@pytest.mark.asyncio
async def test_failed_branch_does_not_erase_successful_sibling():
    batch = await execute_reverse_trace_plan(
        _plan(),
        providers=_registry(),
        trusted_runtime=Runtime(fail_query='"Official Lab" Model X'),
        execution_context=_context(),
        policy_context=_policy(),
        task_id="task:1",
        epoch_id="epoch:1",
        created_at="2026-09-01T00:00:00Z",
    )
    assert batch.complete is False
    assert batch.failure_count == 1
    assert batch.candidate_count == 1
    assert batch.executions[0].status is TraceExecutionStatus.SUCCEEDED
    assert batch.executions[1].status is TraceExecutionStatus.PROVIDER_FAILED
