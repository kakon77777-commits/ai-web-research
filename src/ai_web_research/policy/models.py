from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ai_web_research.core.types import JsonValue, RiskClass
from ai_web_research.execution.models import AuthorizationResult


class AcquisitionAction(StrEnum):
    VIEW = "view"
    MANUAL_QUERY = "manual_query"
    AUTOMATED_QUERY = "automated_query"
    FETCH = "fetch"
    CRAWL = "crawl"
    SCRAPE = "scrape"
    BULK_DOWNLOAD = "bulk_download"
    MONITOR = "monitor"
    TRANSIENT_CACHE = "transient_cache"
    PERSISTENT_CACHE = "persistent_cache"
    BULK_STORE = "bulk_store"
    ARCHIVE = "archive"
    INDEX = "index"
    TRANSFORM = "transform"
    INTERNAL_USE = "internal_use"
    COMMERCIAL_USE = "commercial_use"
    REDISTRIBUTE_RAW = "redistribute_raw"
    DISTRIBUTE_DERIVED = "distribute_derived"
    SUBLICENSE = "sublicense"
    TRAIN_MODEL = "train_model"
    QUOTE = "quote"
    LINK = "link"


class PolicyRuleEffect(StrEnum):
    PERMISSION = "permission"
    PROHIBITION = "prohibition"
    DUTY = "duty"
    CONSTRAINT = "constraint"
    INFO = "info"


@dataclass(frozen=True)
class PolicySourceRef:
    source_id: str
    uri: str | None
    title: str | None
    retrieved_at: str
    effective_at: str | None
    expires_at: str | None
    content_hash: str | None
    anchor: dict[str, JsonValue]
    authority: str
    interpretation_status: str


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    action: AcquisitionAction
    effect: PolicyRuleEffect
    value: JsonValue
    asset_scope: str
    party_scope: str | None
    purpose_scope: tuple[str, ...]
    constraints: dict[str, JsonValue]
    source_refs: tuple[str, ...]
    priority_hint: int = 0


@dataclass(frozen=True)
class SourcePolicyProfile:
    policy_id: str
    version: str
    provider_id: str
    surface_id: str
    asset_scope: str
    rules: tuple[PolicyRule, ...]
    policy_sources: tuple[PolicySourceRef, ...]
    auth_requirements: dict[str, JsonValue]
    rate_limits: dict[str, JsonValue]
    retention_rules: dict[str, JsonValue]
    attribution_rules: dict[str, JsonValue]
    redistribution_rules: dict[str, JsonValue]
    privacy_flags: tuple[str, ...]
    observed_at: str
    effective_at: str | None
    expires_at: str | None
    next_review_at: str | None
    policy_hash: str
    review_status: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def ref(self) -> str:
        return f"{self.policy_id}@{self.version}"


@dataclass(frozen=True)
class RobotsProfile:
    robots_id: str
    provider_id: str
    surface_id: str
    user_agent: str
    uri: str
    fetched_at: str
    status_code: int | None
    allowed: bool | None
    crawl_delay_seconds: float | None
    content_hash: str | None
    fetch_status: str


@dataclass(frozen=True)
class PolicyContext:
    task_id: str
    purpose: str | None
    party_profile_id: str | None
    risk_class: RiskClass
    jurisdiction_context: tuple[str, ...]
    requested_actions: tuple[AcquisitionAction, ...]
    timestamp: str


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    kind: str
    parameters: dict[str, JsonValue]
    persists_downstream: bool
    policy_refs: tuple[str, ...]


@dataclass(frozen=True)
class PolicyLimit:
    limit_id: str
    kind: str
    value: JsonValue
    unit: str | None
    window: str | None
    policy_refs: tuple[str, ...]


@dataclass(frozen=True)
class UsageEnvelopeSeed:
    permissions: tuple[AcquisitionAction, ...] = ()
    prohibitions: tuple[AcquisitionAction, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    limits: tuple[PolicyLimit, ...] = ()
    policy_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class UsageEnvelope:
    envelope_id: str
    asset_ref: str
    permissions: tuple[AcquisitionAction, ...]
    prohibitions: tuple[AcquisitionAction, ...]
    obligations: tuple[Obligation, ...]
    limits: tuple[PolicyLimit, ...]
    source_policy_refs: tuple[str, ...]
    inherited_from: tuple[str, ...]
    created_at: str
    evaluator_version: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyEvaluation:
    authorization: AuthorizationResult
    usage_seed: UsageEnvelopeSeed
    robots_ref: str | None
