from __future__ import annotations

from hashlib import sha256

from .models import (
    ClaimEvidenceAssessment,
    ClaimEvidenceRelation,
    ClaimEvidenceRelationType,
    EvidenceProvenance,
    EvidenceStatus,
    VerifiedEvidence,
)
from .verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)


class ClaimLinkRejected(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(f"claim evidence link rejected: {reason_code}")


def link_evidence_to_claim(
    evidence: VerifiedEvidence,
    claim_id: str,
    relation_type: ClaimEvidenceRelationType,
    semantic_verification: VerificationResult,
    provenance: EvidenceProvenance,
    *,
    created_at: str,
) -> ClaimEvidenceRelation:
    if provenance.evidence_id != evidence.evidence_id:
        raise ClaimLinkRejected("PROVENANCE_EVIDENCE_MISMATCH")
    if semantic_verification.dimension is not VerificationDimension.SEMANTIC_SUPPORT:
        raise ClaimLinkRejected("SEMANTIC_SUPPORT_VERIFICATION_REQUIRED")
    if semantic_verification.decision is not VerificationDecision.PASS:
        raise ClaimLinkRejected("SEMANTIC_SUPPORT_NOT_VERIFIED")
    if semantic_verification.evidence_ref != evidence.evidence_id:
        raise ClaimLinkRejected("SEMANTIC_VERIFICATION_EVIDENCE_MISMATCH")
    if semantic_verification.claim_ref != claim_id:
        raise ClaimLinkRejected("SEMANTIC_VERIFICATION_CLAIM_MISMATCH")

    digest = sha256(
        (
            f"{claim_id}|{evidence.evidence_id}|{relation_type.value}|"
            f"{semantic_verification.verification_id}|{provenance.provenance_id}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    return ClaimEvidenceRelation(
        relation_id=f"claim-evidence:{digest}",
        claim_id=claim_id,
        evidence_id=evidence.evidence_id,
        relation_type=relation_type,
        semantic_verification_ref=semantic_verification.verification_id,
        provenance_ref=provenance.provenance_id,
        confidence=semantic_verification.confidence,
        created_at=created_at,
    )


def assess_claim_evidence(
    claim_id: str,
    relations: tuple[ClaimEvidenceRelation, ...],
    provenances: tuple[EvidenceProvenance, ...],
    *,
    minimum_independent_support_roots: int = 2,
) -> ClaimEvidenceAssessment:
    if minimum_independent_support_roots < 1:
        raise ValueError("minimum_independent_support_roots must be >= 1")

    relevant = tuple(
        relation for relation in relations if relation.claim_id == claim_id
    )
    provenance_by_evidence = {
        provenance.evidence_id: provenance for provenance in provenances
    }

    def evidence_refs(kind: ClaimEvidenceRelationType) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    relation.evidence_id
                    for relation in relevant
                    if relation.relation_type is kind
                }
            )
        )

    support = evidence_refs(ClaimEvidenceRelationType.SUPPORTS)
    contradiction = evidence_refs(ClaimEvidenceRelationType.CONTRADICTS)
    qualification = evidence_refs(ClaimEvidenceRelationType.QUALIFIES)
    background = evidence_refs(ClaimEvidenceRelationType.BACKGROUND)

    def independent_roots(
        kind: ClaimEvidenceRelationType,
    ) -> tuple[str, ...]:
        roots: set[str] = set()
        for relation in relevant:
            if relation.relation_type is not kind:
                continue
            provenance = provenance_by_evidence.get(relation.evidence_id)
            if provenance is None or not provenance.root_resolved:
                continue
            roots.add(provenance.independent_root_ref)
        return tuple(sorted(roots))

    support_roots = independent_roots(ClaimEvidenceRelationType.SUPPORTS)
    contradiction_roots = independent_roots(
        ClaimEvidenceRelationType.CONTRADICTS
    )

    if contradiction_roots:
        status = EvidenceStatus.CONTESTED
    elif len(support_roots) >= minimum_independent_support_roots:
        status = EvidenceStatus.CORROBORATED
    elif qualification and not support:
        status = EvidenceStatus.QUALIFIED
    else:
        status = EvidenceStatus.CLAIM_LINKED

    return ClaimEvidenceAssessment(
        claim_id=claim_id,
        status=status,
        supporting_evidence_refs=support,
        contradicting_evidence_refs=contradiction,
        qualifying_evidence_refs=qualification,
        background_evidence_refs=background,
        independent_support_root_refs=support_roots,
        independent_contradiction_root_refs=contradiction_roots,
    )
