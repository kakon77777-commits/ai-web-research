from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue, SearchAction, VersionRef
from ai_web_research.execution.models import ObservationStatus, PolicyDecision, ProviderObservation
from ai_web_research.gaps.projection import GapProjection
from ai_web_research.policy.models import PolicyEvaluation
from ai_web_research.routing.models import RoutingDecision


class SearchReceiptStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


@dataclass(frozen=True)
class SearchActionReceipt:
    action_receipt_id: str
    task_id: str
    epoch_id: str
    action_id: str

    method_ref: VersionRef
    provider_ref: VersionRef
    surface_id: str
    binding_id: str

    policy_decision: PolicyDecision
    policy_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]

    observation_id: str | None
    observation_status: ObservationStatus | None
    result_count: int | None
    artifact_refs: tuple[str, ...]

    cost: dict[str, JsonValue]
    latency_ms: float | None
    gap_refs: tuple[str, ...]

    occurred_at: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchReceipt:
    receipt_id: str
    task_id: str
    epoch_id: str

    registry_snapshot_id: str
    planner_id: str
    planner_version: str

    actions: tuple[SearchActionReceipt, ...]
    stop_reason: str
    status: SearchReceiptStatus

    created_at: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)


class SearchReceiptRecorder:
    """Persist only externally observable execution facts, never private reasoning."""

    def __init__(self, store) -> None:
        self.store = store

    @staticmethod
    def _id(action: SearchAction) -> str:
        return f"{action.epoch_id}:{action.action_id}:receipt"

    @staticmethod
    def _metadata(base: dict[str, JsonValue], routing_decision: RoutingDecision | None) -> dict[str, JsonValue]:
        metadata = dict(base)
        if routing_decision is not None:
            metadata["routing"] = routing_decision.to_receipt_metadata()
        return metadata

    def record_success(
        self,
        *,
        action: SearchAction,
        evaluation: PolicyEvaluation,
        observation: ProviderObservation,
        gap_projections: tuple[GapProjection, ...] = (),
        routing_decision: RoutingDecision | None = None,
    ) -> SearchActionReceipt:
        receipt = SearchActionReceipt(
            action_receipt_id=self._id(action),
            task_id=action.task_id,
            epoch_id=action.epoch_id,
            action_id=action.action_id,
            method_ref=action.method_ref,
            provider_ref=action.provider_ref,
            surface_id=action.surface_id,
            binding_id=action.binding_id,
            policy_decision=evaluation.authorization.decision,
            policy_refs=evaluation.authorization.policy_refs,
            reason_codes=evaluation.authorization.reason_codes,
            observation_id=observation.observation_id,
            observation_status=observation.status,
            result_count=observation.result_count,
            artifact_refs=tuple(artifact.id for artifact in observation.artifacts),
            cost=dict(observation.cost),
            latency_ms=observation.latency_ms,
            gap_refs=tuple(gap.gap_projection_id for gap in gap_projections),
            occurred_at=observation.occurred_at,
            metadata=self._metadata(
                {"observation_diagnostics": list(observation.diagnostics)},
                routing_decision,
            ),
        )
        self.store.save_search_action_receipt(receipt)
        return receipt

    def record_rejected(
        self,
        *,
        action: SearchAction,
        evaluation: PolicyEvaluation,
        occurred_at: str,
        routing_decision: RoutingDecision | None = None,
    ) -> SearchActionReceipt:
        receipt = SearchActionReceipt(
            action_receipt_id=self._id(action),
            task_id=action.task_id,
            epoch_id=action.epoch_id,
            action_id=action.action_id,
            method_ref=action.method_ref,
            provider_ref=action.provider_ref,
            surface_id=action.surface_id,
            binding_id=action.binding_id,
            policy_decision=evaluation.authorization.decision,
            policy_refs=evaluation.authorization.policy_refs,
            reason_codes=evaluation.authorization.reason_codes,
            observation_id=None,
            observation_status=None,
            result_count=None,
            artifact_refs=(),
            cost={},
            latency_ms=None,
            gap_refs=(),
            occurred_at=occurred_at,
            metadata=self._metadata(
                {"rejected_before_provider_execution": True},
                routing_decision,
            ),
        )
        self.store.save_search_action_receipt(receipt)
        return receipt

    def record_failed(
        self,
        *,
        action: SearchAction,
        evaluation: PolicyEvaluation,
        occurred_at: str,
        exception: Exception,
        routing_decision: RoutingDecision | None = None,
    ) -> SearchActionReceipt:
        receipt = SearchActionReceipt(
            action_receipt_id=self._id(action),
            task_id=action.task_id,
            epoch_id=action.epoch_id,
            action_id=action.action_id,
            method_ref=action.method_ref,
            provider_ref=action.provider_ref,
            surface_id=action.surface_id,
            binding_id=action.binding_id,
            policy_decision=evaluation.authorization.decision,
            policy_refs=evaluation.authorization.policy_refs,
            reason_codes=(
                *evaluation.authorization.reason_codes,
                "PROVIDER_EXECUTION_ERROR",
            ),
            observation_id=None,
            observation_status=ObservationStatus.FAILED,
            result_count=None,
            artifact_refs=(),
            cost={},
            latency_ms=None,
            gap_refs=(),
            occurred_at=occurred_at,
            metadata=self._metadata(
                {
                    "provider_execution_failed": True,
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                },
                routing_decision,
            ),
        )
        self.store.save_search_action_receipt(receipt)
        return receipt

    def finalize(
        self,
        *,
        receipt_id: str,
        task_id: str,
        epoch_id: str,
        registry_snapshot_id: str,
        planner_id: str,
        planner_version: str,
        stop_reason: str,
        status: SearchReceiptStatus,
        created_at: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> SearchReceipt:
        receipt = SearchReceipt(
            receipt_id=receipt_id,
            task_id=task_id,
            epoch_id=epoch_id,
            registry_snapshot_id=registry_snapshot_id,
            planner_id=planner_id,
            planner_version=planner_version,
            actions=self.store.list_search_action_receipts(epoch_id),
            stop_reason=stop_reason,
            status=status,
            created_at=created_at,
            metadata=dict(metadata or {}),
        )
        self.store.save_search_receipt(receipt)
        return receipt
