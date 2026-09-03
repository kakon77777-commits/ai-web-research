from dataclasses import FrozenInstanceError, fields

import pytest

from ai_web_research.evidence.models import (
    ClaimEvidenceAssessment,
    ClaimEvidenceRelation,
    ClaimEvidenceRelationType,
    EvidenceProvenance,
    EvidenceStatus,
    VerifiedEvidence,
)


def verified(**overrides):
    values = dict(
        evidence_id="evidence:1",
        candidate_evidence_id="candidate:1",
        acquired_asset_id="asset:1",
        source_identity_ref="source:a",
        work_identity_ref="work:a",
        version_identity_ref="version:a",
        manifestation_identity_ref="manifestation:a",
        anchor_refs=("anchor:1",),
        verification_refs=("verify:anchor", "verify:source"),
        usage_envelope_id="usage:1",
        status=EvidenceStatus.ANCHORED,
        created_at="2026-09-03T09:00:00+00:00",
        metadata={"promotion_policy_id": "evidence-promotion.v0.6"},
    )
    values.update(overrides)
    return VerifiedEvidence(**values)


def test_claim_relation_types_are_explicit():
    assert [item.value for item in ClaimEvidenceRelationType] == [
        "supports", "contradicts", "qualifies", "background"
    ]


def test_verified_evidence_is_immutable_and_keeps_candidate_asset_policy_lineage():
    item = verified()
    assert item.candidate_evidence_id == "candidate:1"
    assert item.acquired_asset_id == "asset:1"
    assert item.usage_envelope_id == "usage:1"
    assert item.verification_refs == ("verify:anchor", "verify:source")
    with pytest.raises(FrozenInstanceError):
        item.status = EvidenceStatus.CLAIM_LINKED


def test_verified_evidence_rejects_empty_core_identity_or_verification_lineage():
    with pytest.raises(ValueError):
        verified(evidence_id="")
    with pytest.raises(ValueError):
        verified(candidate_evidence_id="")
    with pytest.raises(ValueError):
        verified(acquired_asset_id="")
    with pytest.raises(ValueError):
        verified(usage_envelope_id="")
    with pytest.raises(ValueError):
        verified(verification_refs=())


def test_provenance_requires_explicit_independent_root_ref():
    provenance = EvidenceProvenance(
        provenance_id="provenance:1",
        evidence_id="evidence:1",
        source_identity_ref="source:a",
        source_family_id="family:a",
        independent_root_ref="source:root-a",
        root_resolved=True,
        lineage_relation_refs=("relation:1",),
        created_at="2026-09-03T09:00:00+00:00",
    )
    assert provenance.independent_root_ref == "source:root-a"
    with pytest.raises(ValueError):
        EvidenceProvenance(
            provenance_id="provenance:bad",
            evidence_id="evidence:1",
            source_identity_ref="source:a",
            source_family_id=None,
            independent_root_ref="",
            root_resolved=False,
            lineage_relation_refs=(),
            created_at="2026-09-03T09:00:00+00:00",
        )


def test_claim_evidence_relation_validates_confidence_and_semantic_verification_ref():
    relation = ClaimEvidenceRelation(
        relation_id="claim-rel:1",
        claim_id="claim:1",
        evidence_id="evidence:1",
        relation_type=ClaimEvidenceRelationType.SUPPORTS,
        semantic_verification_ref="verify:semantic:1",
        provenance_ref="provenance:1",
        confidence=0.9,
        created_at="2026-09-03T09:00:00+00:00",
    )
    assert relation.relation_type is ClaimEvidenceRelationType.SUPPORTS

    with pytest.raises(ValueError):
        ClaimEvidenceRelation(
            **{**relation.__dict__, "confidence": 1.1}
        )
    with pytest.raises(ValueError):
        ClaimEvidenceRelation(
            **{**relation.__dict__, "semantic_verification_ref": ""}
        )


def test_claim_assessment_counts_independent_roots_without_raw_citation_count_fields():
    assessment = ClaimEvidenceAssessment(
        claim_id="claim:1",
        status=EvidenceStatus.CORROBORATED,
        supporting_evidence_refs=("evidence:1", "evidence:2"),
        contradicting_evidence_refs=(),
        qualifying_evidence_refs=(),
        background_evidence_refs=(),
        independent_support_root_refs=("source:root-a", "source:root-b"),
        independent_contradiction_root_refs=(),
    )
    assert assessment.independent_support_root_count == 2
    assert assessment.independent_contradiction_root_count == 0

    model_names = set()
    for cls in (
        VerifiedEvidence,
        EvidenceProvenance,
        ClaimEvidenceRelation,
        ClaimEvidenceAssessment,
    ):
        model_names.update(field.name for field in fields(cls))
    assert "citation_supports_claim" not in model_names
    assert "grounded_answer_is_evidence" not in model_names
    assert "provider_rank" not in model_names
