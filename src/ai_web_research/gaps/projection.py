from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.evidence.verifier import VerificationDecision, VerificationDimension, VerificationResult


class EvidenceGapType(StrEnum):
    MISSING_PRIMARY_SOURCE = "missing_primary_source"
    MISSING_INDEPENDENT_SUPPORT = "missing_independent_support"
    MISSING_COUNTER_CHECK = "missing_counter_check"
    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    MISSING_VERSION = "missing_version"
    MISSING_IDENTITY = "missing_identity"
    UNVERIFIED_ANCHOR = "unverified_anchor"
    STALE_EVIDENCE = "stale_evidence"
    POLICY_RESTRICTED_SOURCE = "policy_restricted_source"
    UNVERIFIED_SEMANTIC_SUPPORT = "unverified_semantic_support"
    UNRESOLVED_PROVENANCE = "unresolved_provenance"


@dataclass(frozen=True)
class GapProjection:
    gap_projection_id: str
    claim_id: str | None
    evidence_refs: tuple[str, ...]
    gap_types: tuple[EvidenceGapType, ...]
    mandatory: bool
    severity: float | None
    reason_codes: tuple[str, ...]
    created_at: str


def project_candidate_gaps(
    candidate: CandidateEvidence,
    verifications: tuple[VerificationResult, ...],
    *,
    policy_restricted: bool = False,
    require_source_identity: bool = True,
    require_version: bool = False,
    created_at: str,
) -> GapProjection:
    gap_types: set[EvidenceGapType] = set()
    reason_codes: set[str] = set()

    if require_source_identity and candidate.source_identity_ref is None:
        gap_types.add(EvidenceGapType.MISSING_IDENTITY)
        reason_codes.add("SOURCE_UNRESOLVED")
    if require_version and candidate.version_identity_ref is None:
        gap_types.add(EvidenceGapType.MISSING_VERSION)
        reason_codes.add("VERSION_UNRESOLVED")
    if policy_restricted:
        gap_types.add(EvidenceGapType.POLICY_RESTRICTED_SOURCE)
        reason_codes.add("POLICY_RESTRICTED")

    for verification in verifications:
        if (
            verification.evidence_ref == candidate.candidate_evidence_id
            and verification.dimension is VerificationDimension.ANCHOR
            and verification.decision is VerificationDecision.FAIL
        ):
            gap_types.add(EvidenceGapType.UNVERIFIED_ANCHOR)
            reason_codes.update(verification.reason_codes)

    ordered = tuple(sorted(gap_types, key=lambda item: item.value))
    return GapProjection(
        gap_projection_id=f"{candidate.candidate_evidence_id}:gap",
        claim_id=None,
        evidence_refs=(candidate.candidate_evidence_id,),
        gap_types=ordered,
        mandatory=bool(ordered),
        severity=1.0 if ordered else 0.0,
        reason_codes=tuple(sorted(reason_codes)),
        created_at=created_at,
    )



def project_verified_evidence_gaps(
    evidence,
    provenance,
    *,
    claim_id: str | None,
    semantic_support_verified: bool,
    contested: bool = False,
    created_at: str,
) -> GapProjection:
    gap_types: set[EvidenceGapType] = set()
    reason_codes: set[str] = set()

    if not provenance.root_resolved:
        gap_types.add(EvidenceGapType.UNRESOLVED_PROVENANCE)
        reason_codes.add("INDEPENDENT_ROOT_UNRESOLVED")

    if claim_id is not None and not semantic_support_verified:
        gap_types.add(EvidenceGapType.UNVERIFIED_SEMANTIC_SUPPORT)
        reason_codes.add("SEMANTIC_SUPPORT_NOT_VERIFIED")

    if contested:
        gap_types.add(EvidenceGapType.UNRESOLVED_CONTRADICTION)
        reason_codes.add("CLAIM_EVIDENCE_CONTESTED")

    ordered = tuple(sorted(gap_types, key=lambda item: item.value))
    claim_suffix = claim_id if claim_id is not None else "unlinked"
    return GapProjection(
        gap_projection_id=f"{evidence.evidence_id}:closure-gap:{claim_suffix}",
        claim_id=claim_id,
        evidence_refs=(evidence.evidence_id,),
        gap_types=ordered,
        mandatory=bool(ordered),
        severity=1.0 if ordered else 0.0,
        reason_codes=tuple(sorted(reason_codes)),
        created_at=created_at,
    )
