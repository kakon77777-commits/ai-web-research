from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ai_web_research.core.types import JsonValue
from ai_web_research.execution.models import ErrorCategory, RuntimeErrorRecord


class OmphalosErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PLAN_INVALID = "PLAN_INVALID"
    BINDING_UNAVAILABLE = "BINDING_UNAVAILABLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NORMALIZATION_ERROR = "NORMALIZATION_ERROR"
    EVIDENCE_VERIFICATION_FAILED = "EVIDENCE_VERIFICATION_FAILED"
    STORAGE_CONFLICT = "STORAGE_CONFLICT"
    REPLAY_MISMATCH = "REPLAY_MISMATCH"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ErrorDescriptor:
    code: OmphalosErrorCode
    category: ErrorCategory
    recoverable: bool
    description: str


ERROR_CATALOG = {
    OmphalosErrorCode.VALIDATION_ERROR: ErrorDescriptor(
        OmphalosErrorCode.VALIDATION_ERROR, ErrorCategory.VALIDATION, False,
        "Input or contract validation failed.",
    ),
    OmphalosErrorCode.PLAN_INVALID: ErrorDescriptor(
        OmphalosErrorCode.PLAN_INVALID, ErrorCategory.VALIDATION, False,
        "Search plan validation failed.",
    ),
    OmphalosErrorCode.BINDING_UNAVAILABLE: ErrorDescriptor(
        OmphalosErrorCode.BINDING_UNAVAILABLE, ErrorCategory.VALIDATION, True,
        "No eligible executable binding is currently available.",
    ),
    OmphalosErrorCode.POLICY_BLOCKED: ErrorDescriptor(
        OmphalosErrorCode.POLICY_BLOCKED, ErrorCategory.POLICY, False,
        "Policy evaluation blocked execution.",
    ),
    OmphalosErrorCode.HUMAN_REVIEW_REQUIRED: ErrorDescriptor(
        OmphalosErrorCode.HUMAN_REVIEW_REQUIRED, ErrorCategory.POLICY, False,
        "Execution requires explicit human review.",
    ),
    OmphalosErrorCode.AUTH_REQUIRED: ErrorDescriptor(
        OmphalosErrorCode.AUTH_REQUIRED, ErrorCategory.AUTH, True,
        "The selected execution channel requires authentication.",
    ),
    OmphalosErrorCode.CREDENTIAL_UNAVAILABLE: ErrorDescriptor(
        OmphalosErrorCode.CREDENTIAL_UNAVAILABLE, ErrorCategory.AUTH, True,
        "A required credential profile is unavailable.",
    ),
    OmphalosErrorCode.PROVIDER_UNAVAILABLE: ErrorDescriptor(
        OmphalosErrorCode.PROVIDER_UNAVAILABLE, ErrorCategory.PROVIDER, True,
        "The selected Provider or Surface is unavailable.",
    ),
    OmphalosErrorCode.QUOTA_EXHAUSTED: ErrorDescriptor(
        OmphalosErrorCode.QUOTA_EXHAUSTED, ErrorCategory.RATE_LIMIT, True,
        "Provider quota is exhausted for the current window.",
    ),
    OmphalosErrorCode.RATE_LIMITED: ErrorDescriptor(
        OmphalosErrorCode.RATE_LIMITED, ErrorCategory.RATE_LIMIT, True,
        "Provider rate limit prevented execution.",
    ),
    OmphalosErrorCode.TIMEOUT: ErrorDescriptor(
        OmphalosErrorCode.TIMEOUT, ErrorCategory.TIMEOUT, True,
        "Execution exceeded its time limit.",
    ),
    OmphalosErrorCode.NETWORK_ERROR: ErrorDescriptor(
        OmphalosErrorCode.NETWORK_ERROR, ErrorCategory.NETWORK, True,
        "Network transport failed.",
    ),
    OmphalosErrorCode.PROVIDER_ERROR: ErrorDescriptor(
        OmphalosErrorCode.PROVIDER_ERROR, ErrorCategory.PROVIDER, True,
        "Provider execution returned an error.",
    ),
    OmphalosErrorCode.NORMALIZATION_ERROR: ErrorDescriptor(
        OmphalosErrorCode.NORMALIZATION_ERROR, ErrorCategory.NORMALIZATION, False,
        "Provider output could not be normalized into the declared contract.",
    ),
    OmphalosErrorCode.EVIDENCE_VERIFICATION_FAILED: ErrorDescriptor(
        OmphalosErrorCode.EVIDENCE_VERIFICATION_FAILED,
        ErrorCategory.NORMALIZATION,
        False,
        "Evidence verification failed its declared verification gate.",
    ),
    OmphalosErrorCode.STORAGE_CONFLICT: ErrorDescriptor(
        OmphalosErrorCode.STORAGE_CONFLICT, ErrorCategory.STORAGE, False,
        "An immutable stored identity conflicts with an existing payload.",
    ),
    OmphalosErrorCode.REPLAY_MISMATCH: ErrorDescriptor(
        OmphalosErrorCode.REPLAY_MISMATCH, ErrorCategory.VALIDATION, False,
        "Replay inputs or outputs do not match the recorded snapshot.",
    ),
    OmphalosErrorCode.INTERNAL_ERROR: ErrorDescriptor(
        OmphalosErrorCode.INTERNAL_ERROR, ErrorCategory.INTERNAL, False,
        "Unexpected internal Runtime failure.",
    ),
}


_SENSITIVE_MARKERS = (
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "password",
    "credential_value",
)


def _validate_safe_metadata(value, path: str = "metadata") -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower().replace("-", "_")
            if any(marker in key for marker in _SENSITIVE_MARKERS):
                raise ValueError(f"sensitive metadata key is not allowed: {path}.{raw_key}")
            _validate_safe_metadata(nested, f"{path}.{raw_key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_safe_metadata(nested, f"{path}[{index}]")


class OmphalosError(RuntimeError):
    def __init__(
        self,
        code: OmphalosErrorCode,
        message: str,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> None:
        if code not in ERROR_CATALOG:
            raise ValueError(f"unknown Omphalos error code: {code}")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be non-empty")
        safe_metadata = dict(metadata or {})
        _validate_safe_metadata(safe_metadata)
        self.code = code
        self.message = message
        self.metadata = safe_metadata
        super().__init__(message)

    @property
    def descriptor(self) -> ErrorDescriptor:
        return ERROR_CATALOG[self.code]

    def to_runtime_record(
        self,
        *,
        action_id: str | None = None,
        provider_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> RuntimeErrorRecord:
        return RuntimeErrorRecord(
            code=self.code.value,
            category=self.descriptor.category,
            message=self.message,
            recoverable=self.descriptor.recoverable,
            action_id=action_id,
            provider_id=provider_id,
            retry_after_seconds=retry_after_seconds,
            metadata=dict(self.metadata),
        )
