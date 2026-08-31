from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from ai_web_research.policy.models import UsageEnvelopeSeed

from ai_web_research.core.types import ArtifactRef, JsonValue, SearchAction


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    ALLOW_WITH_OBLIGATIONS = "allow_with_obligations"
    DENY = "deny"
    UNKNOWN = "unknown"
    REVIEW = "review"


@dataclass(frozen=True)
class AuthorizationResult:
    decision: PolicyDecision
    obligations: tuple[str, ...] = ()
    limits: dict[str, JsonValue] = field(default_factory=dict)
    policy_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @property
    def is_executable(self) -> bool:
        return self.decision in {
            PolicyDecision.ALLOW,
            PolicyDecision.ALLOW_WITH_OBLIGATIONS,
        }


@dataclass(frozen=True)
class AuthorizedAction:
    action: SearchAction
    authorization: AuthorizationResult
    credential_profile_id: str | None = None
    usage_seed: "UsageEnvelopeSeed | None" = None


@dataclass
class ExecutionContext:
    task_id: str
    epoch_id: str
    registry_snapshot_id: str
    services: Mapping[str, object] = field(default_factory=dict)
    runtime_limits: dict[str, JsonValue] = field(default_factory=dict)


class ObservationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True)
class ProviderObservation:
    observation_id: str
    action_id: str
    provider_id: str
    surface_id: str
    status: ObservationStatus
    artifacts: tuple[ArtifactRef, ...]
    raw_ref: str | None
    result_count: int | None
    cost: dict[str, JsonValue]
    latency_ms: float | None
    continuation: dict[str, JsonValue]
    diagnostics: tuple[str, ...]
    occurred_at: str
    metadata: dict[str, JsonValue]


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    POLICY = "policy"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PROVIDER = "provider"
    NETWORK = "network"
    NORMALIZATION = "normalization"
    STORAGE = "storage"
    INTERNAL = "internal"


@dataclass(frozen=True)
class RuntimeErrorRecord:
    code: str
    category: ErrorCategory
    message: str
    recoverable: bool
    action_id: str | None
    provider_id: str | None
    retry_after_seconds: float | None
    metadata: dict[str, JsonValue]
