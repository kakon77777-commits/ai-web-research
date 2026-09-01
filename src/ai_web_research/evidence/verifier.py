from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VerificationDimension(StrEnum):
    SOURCE_IDENTITY = "source_identity"
    WORK_IDENTITY = "work_identity"
    VERSION_IDENTITY = "version_identity"
    FIXITY = "fixity"
    ANCHOR = "anchor"
    TEMPORAL = "temporal"
    SEMANTIC_SUPPORT = "semantic_support"
    INDEPENDENCE = "independence"
    POLICY = "policy"


class VerificationDecision(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    REVIEW = "review"


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    evidence_ref: str
    claim_ref: str | None
    dimension: VerificationDimension
    decision: VerificationDecision
    reason_codes: tuple[str, ...]
    verifier_id: str
    verifier_version: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    confidence: float | None
    created_at: str
