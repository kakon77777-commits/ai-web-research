from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.discovery.models import DiscoveryBatch
from ai_web_research.discovery.normalize import normalize_discovery_observation
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.trusted import TrustedExecutionRejected
from ai_web_research.policy.models import PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding

from .trace import ReverseTracePlan, TraceAction, TraceActionKind

LEXICAL_METHOD = VersionRef("method.lexical_search", "1.0.0")
RUNNER_ID = "reverse_trace.runner.v0.1"


class TraceExecutionError(RuntimeError):
    pass


class TraceExecutionUnavailable(TraceExecutionError):
    pass


class TraceActionNotSearchable(TraceExecutionError):
    pass


@dataclass(frozen=True)
class TraceSearchAction:
    source_id: str
    trace_action_id: str
    trace_kind: TraceActionKind
    signal: str
    search_action: SearchAction


class TraceExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    POLICY_REJECTED = "policy_rejected"
    PROVIDER_FAILED = "provider_failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TraceSearchExecution:
    source_id: str
    trace_action_id: str
    trace_kind: TraceActionKind
    search_action_id: str
    provider_id: str
    binding_id: str
    status: TraceExecutionStatus
    discovery_batch: DiscoveryBatch | None
    observation_id: str | None
    error_code: str | None


@dataclass(frozen=True)
class TraceExecutionBatch:
    source_id: str
    executions: tuple[TraceSearchExecution, ...]
    skipped_action_ids: tuple[str, ...]
    complete: bool

    @property
    def failure_count(self) -> int:
        return sum(
            1
            for execution in self.executions
            if execution.status is not TraceExecutionStatus.SUCCEEDED
        )

    @property
    def candidate_count(self) -> int:
        return sum(
            len(execution.discovery_batch.candidates)
            for execution in self.executions
            if execution.discovery_batch is not None
        )


def select_lexical_binding(
    providers: ProviderRegistrySnapshot,
    provider_preferences: tuple[str, ...] = (),
) -> MethodBinding:
    preference_rank = {
        provider_id: index for index, provider_id in enumerate(provider_preferences)
    }
    compatible: list[MethodBinding] = []
    for binding in providers.bindings:
        if not binding.enabled or binding.method_ref != LEXICAL_METHOD:
            continue
        try:
            providers.get_provider(binding.provider_ref)
            providers.surface(binding.provider_ref, binding.surface_id)
        except KeyError:
            continue
        compatible.append(binding)
    if not compatible:
        raise TraceExecutionUnavailable("no enabled lexical-search binding is available")
    compatible.sort(
        key=lambda binding: (
            preference_rank.get(binding.provider_ref.id, len(preference_rank)),
            binding.provider_ref.id,
            binding.binding_id,
        )
    )
    return compatible[0]


def _search_action_id(
    source_id: str,
    trace: TraceAction,
    binding: MethodBinding,
    epoch_id: str,
) -> str:
    digest = sha256(
        f"{source_id}|{trace.action_id}|{binding.binding_id}|{epoch_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"reverse-trace-search:{digest}"


def compile_trace_search_action(
    *,
    source_id: str,
    trace: TraceAction,
    binding: MethodBinding,
    task_id: str,
    epoch_id: str,
    created_at: str,
    top_k: int = 10,
) -> TraceSearchAction:
    if trace.kind not in {
        TraceActionKind.EXACT_QUOTE_SEARCH,
        TraceActionKind.ENTITY_SEARCH,
    }:
        raise TraceActionNotSearchable(
            f"trace action is not lexical-searchable: {trace.kind.value}"
        )
    if not isinstance(trace.query, str) or not trace.query.strip():
        raise TraceActionNotSearchable(
            "searchable trace action requires a non-empty query"
        )
    if binding.method_ref != LEXICAL_METHOD or not binding.enabled:
        raise TraceExecutionUnavailable(
            "binding is not an enabled lexical-search binding"
        )
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    action_id = _search_action_id(source_id, trace, binding, epoch_id)
    search_action = SearchAction(
        action_id=action_id,
        task_id=task_id,
        epoch_id=epoch_id,
        method_ref=LEXICAL_METHOD,
        provider_ref=binding.provider_ref,
        surface_id=binding.surface_id,
        binding_id=binding.binding_id,
        action_kind=ActionKind.SEARCH,
        inputs=(
            ArtifactRef(
                kind=ArtifactKind.QUERY,
                id=f"{trace.action_id}:query",
                metadata={
                    "source_id": source_id,
                    "trace_action_id": trace.action_id,
                    "trace_kind": trace.kind.value,
                },
            ),
        ),
        parameters={"query": trace.query.strip(), "top_k": top_k},
        guards=(),
        expected_effects=("candidate_set_created", "source_frontier_expanded"),
        created_by=RUNNER_ID,
        created_at=created_at,
    )
    return TraceSearchAction(
        source_id=source_id,
        trace_action_id=trace.action_id,
        trace_kind=trace.kind,
        signal=trace.signal,
        search_action=search_action,
    )


async def execute_trace_search_action(
    compiled: TraceSearchAction,
    *,
    trusted_runtime: Any,
    execution_context: ExecutionContext,
    policy_context: PolicyContext,
    credential_profile_id: str | None = None,
    fail_fast: bool = True,
) -> TraceSearchExecution:
    action = compiled.search_action
    try:
        trusted_result = await trusted_runtime.execute(
            action,
            execution_context,
            policy_context,
            credential_profile_id=credential_profile_id,
        )
    except TrustedExecutionRejected as exc:
        if fail_fast:
            raise
        return TraceSearchExecution(
            source_id=compiled.source_id,
            trace_action_id=compiled.trace_action_id,
            trace_kind=compiled.trace_kind,
            search_action_id=action.action_id,
            provider_id=action.provider_ref.id,
            binding_id=action.binding_id,
            status=TraceExecutionStatus.POLICY_REJECTED,
            discovery_batch=None,
            observation_id=None,
            error_code=type(exc).__name__,
        )
    except Exception as exc:
        if fail_fast:
            raise
        return TraceSearchExecution(
            source_id=compiled.source_id,
            trace_action_id=compiled.trace_action_id,
            trace_kind=compiled.trace_kind,
            search_action_id=action.action_id,
            provider_id=action.provider_ref.id,
            binding_id=action.binding_id,
            status=TraceExecutionStatus.PROVIDER_FAILED,
            discovery_batch=None,
            observation_id=None,
            error_code=type(exc).__name__,
        )

    observation = trusted_result.observation
    discovery_batch = normalize_discovery_observation(observation)
    return TraceSearchExecution(
        source_id=compiled.source_id,
        trace_action_id=compiled.trace_action_id,
        trace_kind=compiled.trace_kind,
        search_action_id=action.action_id,
        provider_id=action.provider_ref.id,
        binding_id=action.binding_id,
        status=TraceExecutionStatus.SUCCEEDED,
        discovery_batch=discovery_batch,
        observation_id=observation.observation_id,
        error_code=None,
    )


async def execute_reverse_trace_plan(
    plan: ReverseTracePlan,
    *,
    providers: ProviderRegistrySnapshot,
    trusted_runtime: Any,
    execution_context: ExecutionContext,
    policy_context: PolicyContext,
    task_id: str,
    epoch_id: str,
    created_at: str,
    provider_preferences: tuple[str, ...] = (),
    top_k: int = 10,
    credential_profile_id: str | None = None,
) -> TraceExecutionBatch:
    searchable = tuple(
        action
        for action in plan.actions
        if action.kind
        in {TraceActionKind.EXACT_QUOTE_SEARCH, TraceActionKind.ENTITY_SEARCH}
    )
    skipped = tuple(
        action.action_id
        for action in plan.actions
        if action.kind is TraceActionKind.DIRECT_PREDECESSOR
    )
    if not searchable:
        return TraceExecutionBatch(
            source_id=plan.source_id,
            executions=(),
            skipped_action_ids=skipped,
            complete=True,
        )

    try:
        binding = select_lexical_binding(
            providers,
            provider_preferences=provider_preferences,
        )
    except TraceExecutionUnavailable:
        executions = tuple(
            TraceSearchExecution(
                source_id=plan.source_id,
                trace_action_id=trace.action_id,
                trace_kind=trace.kind,
                search_action_id=f"{trace.action_id}:unavailable",
                provider_id="",
                binding_id="",
                status=TraceExecutionStatus.UNAVAILABLE,
                discovery_batch=None,
                observation_id=None,
                error_code="TraceExecutionUnavailable",
            )
            for trace in searchable
        )
        return TraceExecutionBatch(
            source_id=plan.source_id,
            executions=executions,
            skipped_action_ids=skipped,
            complete=False,
        )

    executions: list[TraceSearchExecution] = []
    for trace in plan.actions:
        if trace.kind not in {
            TraceActionKind.EXACT_QUOTE_SEARCH,
            TraceActionKind.ENTITY_SEARCH,
        }:
            continue
        compiled = compile_trace_search_action(
            source_id=plan.source_id,
            trace=trace,
            binding=binding,
            task_id=task_id,
            epoch_id=epoch_id,
            created_at=created_at,
            top_k=top_k,
        )
        executions.append(
            await execute_trace_search_action(
                compiled,
                trusted_runtime=trusted_runtime,
                execution_context=execution_context,
                policy_context=policy_context,
                credential_profile_id=credential_profile_id,
                fail_fast=False,
            )
        )

    result_tuple = tuple(executions)
    return TraceExecutionBatch(
        source_id=plan.source_id,
        executions=result_tuple,
        skipped_action_ids=skipped,
        complete=all(
            execution.status is TraceExecutionStatus.SUCCEEDED
            for execution in result_tuple
        ),
    )
