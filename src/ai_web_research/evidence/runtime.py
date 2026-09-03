from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ai_web_research.gaps.projection import (
    GapProjection,
    project_verified_evidence_gaps,
)
from ai_web_research.source_graph.models import (
    SourceFamilyResolution,
    SourceRelation,
)

from .claim_links import assess_claim_evidence, link_evidence_to_claim
from .closure import EvidencePromotionPolicy, promote_candidate_evidence
from .ledger import EvidenceLedger
from .models import (
    CandidateEvidence,
    ClaimEvidenceAssessment,
    ClaimEvidenceRelation,
    ClaimEvidenceRelationType,
    EvidenceProvenance,
    EvidenceStatus,
    VerifiedEvidence,
)
from .provenance import resolve_evidence_provenance
from .store import EvidenceClosureStore
from .verifier import VerificationResult


@dataclass(frozen=True)
class EvidenceClosureResult:
    evidence: VerifiedEvidence
    provenance: EvidenceProvenance
    claim_relation: ClaimEvidenceRelation | None
    claim_assessment: ClaimEvidenceAssessment | None
    gap_projection: GapProjection


class EvidenceClosureRuntime:
    runtime_id = "evidence.closure.v0.6"
    runtime_version = "0.6.0"

    def __init__(self, store) -> None:
        self.store = store
        self.closure_store = EvidenceClosureStore(store)
        self.ledger = EvidenceLedger(store)

    def _append(
        self,
        *,
        event_id: str,
        event_type: str,
        subject_type: str,
        subject_id: str,
        input_refs: tuple[str, ...],
        output_refs: tuple[str, ...],
        payload: dict,
        created_at: str,
    ) -> None:
        self.ledger.append(
            event_id=event_id,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            actor_id=self.runtime_id,
            actor_version=self.runtime_version,
            input_refs=input_refs,
            output_refs=output_refs,
            payload=payload,
            created_at=created_at,
        )

    def _record_verification(self, verification: VerificationResult) -> None:
        self.closure_store.save_verification_result(verification)
        self._append(
            event_id=f"{verification.verification_id}:event:recorded",
            event_type="VERIFICATION_RECORDED",
            subject_type="verification",
            subject_id=verification.verification_id,
            input_refs=verification.input_refs,
            output_refs=(verification.verification_id,),
            payload={
                "evidence_ref": verification.evidence_ref,
                "claim_ref": verification.claim_ref,
                "dimension": verification.dimension.value,
                "decision": verification.decision.value,
                "reason_codes": list(verification.reason_codes),
            },
            created_at=verification.created_at,
        )

    def close(
        self,
        candidate: CandidateEvidence,
        verifications: tuple[VerificationResult, ...],
        family_resolution: SourceFamilyResolution,
        *,
        source_relations: tuple[SourceRelation, ...] = (),
        promotion_policy: EvidencePromotionPolicy | None = None,
        claim_id: str | None = None,
        relation_type: ClaimEvidenceRelationType | None = None,
        semantic_verification: VerificationResult | None = None,
        minimum_independent_support_roots: int = 2,
        created_at: str,
    ) -> EvidenceClosureResult:
        # Evidence cannot detach from the usage/policy envelope created at acquisition.
        self.store.get_usage_envelope(candidate.usage_envelope_id)

        promotion_policy = promotion_policy or EvidencePromotionPolicy(
            "evidence-promotion.v0.6"
        )
        if not promotion_policy.require_source_identity:
            raise ValueError(
                "EvidenceClosureRuntime requires source identity verification "
                "for provenance closure"
            )

        unique_verifications: dict[str, VerificationResult] = {
            item.verification_id: item for item in verifications
        }
        if semantic_verification is not None:
            unique_verifications[semantic_verification.verification_id] = (
                semantic_verification
            )
        ordered_verifications = tuple(
            unique_verifications[key] for key in sorted(unique_verifications)
        )
        for verification in ordered_verifications:
            self._record_verification(verification)

        evidence = promote_candidate_evidence(
            candidate,
            verifications,
            promotion_policy,
            created_at=created_at,
        )
        self.closure_store.save_verified_evidence(evidence)
        self._append(
            event_id=f"{evidence.evidence_id}:event:promoted",
            event_type="EVIDENCE_PROMOTED",
            subject_type="verified_evidence",
            subject_id=evidence.evidence_id,
            input_refs=(candidate.candidate_evidence_id, *evidence.verification_refs),
            output_refs=(evidence.evidence_id,),
            payload={
                "candidate_evidence_id": candidate.candidate_evidence_id,
                "usage_envelope_id": evidence.usage_envelope_id,
                "status": evidence.status.value,
            },
            created_at=created_at,
        )

        provenance = resolve_evidence_provenance(
            evidence,
            family_resolution,
            source_relations,
        )
        self.closure_store.save_evidence_provenance(provenance)
        self._append(
            event_id=f"{provenance.provenance_id}:event:attached",
            event_type="PROVENANCE_ATTACHED",
            subject_type="verified_evidence",
            subject_id=evidence.evidence_id,
            input_refs=(evidence.evidence_id, *provenance.lineage_relation_refs),
            output_refs=(provenance.provenance_id,),
            payload={
                "source_identity_ref": provenance.source_identity_ref,
                "source_family_id": provenance.source_family_id,
                "independent_root_ref": provenance.independent_root_ref,
                "root_resolved": provenance.root_resolved,
            },
            created_at=created_at,
        )

        claim_relation = None
        claim_assessment = None

        if semantic_verification is not None and relation_type is None:
            raise ValueError(
                "relation_type is required when semantic_verification is supplied"
            )

        if claim_id is not None and semantic_verification is not None:
            claim_relation = link_evidence_to_claim(
                evidence,
                claim_id,
                relation_type,
                semantic_verification,
                provenance,
                created_at=created_at,
            )
            self.closure_store.save_claim_evidence_relation(claim_relation)
            self._append(
                event_id=f"{claim_relation.relation_id}:event:linked",
                event_type="CLAIM_EVIDENCE_LINKED",
                subject_type="claim",
                subject_id=claim_id,
                input_refs=(
                    evidence.evidence_id,
                    semantic_verification.verification_id,
                    provenance.provenance_id,
                ),
                output_refs=(claim_relation.relation_id,),
                payload={
                    "relation_type": claim_relation.relation_type.value,
                    "confidence": claim_relation.confidence,
                },
                created_at=created_at,
            )

        if claim_id is not None:
            stored_relations = self.closure_store.list_claim_evidence_relations(claim_id)
            if stored_relations:
                stored_provenances = tuple(
                    self.closure_store.get_evidence_provenance(relation.provenance_ref)
                    for relation in stored_relations
                )
                claim_assessment = assess_claim_evidence(
                    claim_id,
                    stored_relations,
                    stored_provenances,
                    minimum_independent_support_roots=(
                        minimum_independent_support_roots
                    ),
                )

                if claim_assessment.status in {
                    EvidenceStatus.CORROBORATED,
                    EvidenceStatus.CONTESTED,
                }:
                    assessment_material = "|".join(
                        (
                            claim_id,
                            claim_assessment.status.value,
                            *claim_assessment.independent_support_root_refs,
                            *claim_assessment.independent_contradiction_root_refs,
                        )
                    )
                    digest = sha256(
                        assessment_material.encode("utf-8")
                    ).hexdigest()[:20]
                    event_type = (
                        "CLAIM_CORROBORATED"
                        if claim_assessment.status is EvidenceStatus.CORROBORATED
                        else "CLAIM_CONTESTED"
                    )
                    self._append(
                        event_id=f"claim-assessment:{digest}",
                        event_type=event_type,
                        subject_type="claim",
                        subject_id=claim_id,
                        input_refs=tuple(
                            relation.relation_id for relation in stored_relations
                        ),
                        output_refs=(),
                        payload={
                            "status": claim_assessment.status.value,
                            "independent_support_root_count": (
                                claim_assessment.independent_support_root_count
                            ),
                            "independent_contradiction_root_count": (
                                claim_assessment.independent_contradiction_root_count
                            ),
                        },
                        created_at=created_at,
                    )

        gap_projection = project_verified_evidence_gaps(
            evidence,
            provenance,
            claim_id=claim_id,
            semantic_support_verified=claim_relation is not None,
            contested=(
                claim_assessment is not None
                and claim_assessment.status is EvidenceStatus.CONTESTED
            ),
            created_at=created_at,
        )
        self.store.save_gap_projection(gap_projection)
        if gap_projection.gap_types:
            self._append(
                event_id=f"{gap_projection.gap_projection_id}:event",
                event_type="GAP_PROJECTED",
                subject_type="gap_projection",
                subject_id=gap_projection.gap_projection_id,
                input_refs=(evidence.evidence_id,),
                output_refs=(gap_projection.gap_projection_id,),
                payload={
                    "gap_types": [
                        gap.value for gap in gap_projection.gap_types
                    ],
                    "reason_codes": list(gap_projection.reason_codes),
                },
                created_at=created_at,
            )

        return EvidenceClosureResult(
            evidence=evidence,
            provenance=provenance,
            claim_relation=claim_relation,
            claim_assessment=claim_assessment,
            gap_projection=gap_projection,
        )
