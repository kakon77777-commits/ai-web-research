from __future__ import annotations

from dataclasses import dataclass

from .models import CandidateEvidence, EvidenceStatus, VerifiedEvidence
from .verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)


@dataclass(frozen=True)
class EvidencePromotionPolicy:
    policy_id: str
    require_anchor: bool = True
    require_source_identity: bool = True
    require_fixity: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id must be non-empty")
        if not (self.require_anchor or self.require_source_identity or self.require_fixity):
            raise ValueError("at least one verification dimension must be required")

    @property
    def required_dimensions(self) -> tuple[VerificationDimension, ...]:
        result: list[VerificationDimension] = []
        if self.require_anchor:
            result.append(VerificationDimension.ANCHOR)
        if self.require_source_identity:
            result.append(VerificationDimension.SOURCE_IDENTITY)
        if self.require_fixity:
            result.append(VerificationDimension.FIXITY)
        return tuple(result)


@dataclass(frozen=True)
class EvidencePromotionDecision:
    promotable: bool
    reason_codes: tuple[str, ...]
    required_dimensions: tuple[VerificationDimension, ...]
    passed_dimensions: tuple[VerificationDimension, ...]


class EvidencePromotionRejected(RuntimeError):
    def __init__(self, decision: EvidencePromotionDecision) -> None:
        self.decision = decision
        super().__init__("evidence promotion rejected: " + ",".join(decision.reason_codes))


def _matching(
    candidate: CandidateEvidence,
    verifications: tuple[VerificationResult, ...],
    dimension: VerificationDimension,
) -> tuple[VerificationResult, ...]:
    return tuple(
        sorted(
            (
                item
                for item in verifications
                if item.evidence_ref == candidate.candidate_evidence_id
                and item.dimension is dimension
            ),
            key=lambda item: item.verification_id,
        )
    )


def evaluate_evidence_promotion(
    candidate: CandidateEvidence,
    verifications: tuple[VerificationResult, ...],
    policy: EvidencePromotionPolicy,
) -> EvidencePromotionDecision:
    required = policy.required_dimensions
    if not isinstance(candidate, CandidateEvidence):
        return EvidencePromotionDecision(
            promotable=False,
            reason_codes=("NOT_CANDIDATE_EVIDENCE",),
            required_dimensions=required,
            passed_dimensions=(),
        )

    reasons: list[str] = []
    passed: list[VerificationDimension] = []

    if candidate.source_type == "llm_recall":
        reasons.append("LLM_RECALL_NOT_EXTERNAL_EVIDENCE")

    if policy.require_anchor and not candidate.anchor_refs:
        reasons.append("MISSING_ANCHOR")
    if policy.require_source_identity and not candidate.source_identity_ref:
        reasons.append("MISSING_SOURCE_IDENTITY")

    for dimension in required:
        rows = _matching(candidate, verifications, dimension)
        blocking = next(
            (
                item
                for item in rows
                if item.decision in {
                    VerificationDecision.FAIL,
                    VerificationDecision.REVIEW,
                }
            ),
            None,
        )
        if blocking is not None:
            reasons.append(
                f"{dimension.value.upper()}_{blocking.decision.value.upper()}"
            )
            continue

        if any(item.decision is VerificationDecision.PASS for item in rows):
            passed.append(dimension)
        else:
            reasons.append(f"{dimension.value.upper()}_NOT_VERIFIED")

    return EvidencePromotionDecision(
        promotable=not reasons,
        reason_codes=tuple(dict.fromkeys(reasons)),
        required_dimensions=required,
        passed_dimensions=tuple(passed),
    )


def promote_candidate_evidence(
    candidate: CandidateEvidence,
    verifications: tuple[VerificationResult, ...],
    policy: EvidencePromotionPolicy,
    *,
    created_at: str,
) -> VerifiedEvidence:
    decision = evaluate_evidence_promotion(candidate, verifications, policy)
    if not decision.promotable:
        raise EvidencePromotionRejected(decision)

    verification_refs: list[str] = []
    for dimension in decision.required_dimensions:
        passed = next(
            item
            for item in _matching(candidate, verifications, dimension)
            if item.decision is VerificationDecision.PASS
        )
        verification_refs.append(passed.verification_id)

    if policy.require_fixity:
        status = EvidenceStatus.FIXITY_VERIFIED
    elif policy.require_anchor:
        status = EvidenceStatus.ANCHORED
    else:
        status = EvidenceStatus.IDENTIFIED

    return VerifiedEvidence(
        evidence_id=f"{candidate.candidate_evidence_id}:verified",
        candidate_evidence_id=candidate.candidate_evidence_id,
        acquired_asset_id=candidate.acquired_asset_id,
        source_identity_ref=candidate.source_identity_ref,
        work_identity_ref=candidate.work_identity_ref,
        version_identity_ref=candidate.version_identity_ref,
        manifestation_identity_ref=candidate.manifestation_identity_ref,
        anchor_refs=candidate.anchor_refs,
        verification_refs=tuple(verification_refs),
        usage_envelope_id=candidate.usage_envelope_id,
        status=status,
        created_at=created_at,
        metadata={
            "promotion_policy_id": policy.policy_id,
            "required_dimensions": [
                dimension.value for dimension in decision.required_dimensions
            ],
            "semantic_support_verified": False,
            "claim_support_not_assessed": True,
        },
    )
