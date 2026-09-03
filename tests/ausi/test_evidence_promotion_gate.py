import pytest

from ai_web_research.evidence.closure import (
    EvidencePromotionPolicy,
    EvidencePromotionRejected,
    evaluate_evidence_promotion,
    promote_candidate_evidence,
)
from ai_web_research.evidence.models import CandidateEvidence, EvidenceStatus
from ai_web_research.evidence.verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)


NOW = "2026-09-03T09:10:00+00:00"


def candidate(**overrides):
    values = dict(
        candidate_evidence_id="candidate:1",
        acquired_asset_id="asset:1",
        field_name="answer",
        extracted_value="42",
        source_identity_ref="source:a",
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=("anchor:1",),
        extraction_method="method.extract_candidate_evidence",
        extractor_version="extractor/1",
        model_ref="model-x",
        source_type="web_crawled_extraction",
        usage_envelope_id="usage:1",
        extractor_confidence=0.9,
        semantic_support_verified=False,
        validation_notes=(),
        created_at=NOW,
    )
    values.update(overrides)
    return CandidateEvidence(**values)


def verification(dimension, decision=VerificationDecision.PASS, *, vid=None):
    return VerificationResult(
        verification_id=vid or f"verify:{dimension.value}:{decision.value}",
        evidence_ref="candidate:1",
        claim_ref=None,
        dimension=dimension,
        decision=decision,
        reason_codes=(f"{dimension.value.upper()}_{decision.value.upper()}",),
        verifier_id="test.verifier",
        verifier_version="1.0",
        input_refs=("candidate:1",),
        output_refs=(),
        confidence=1.0 if decision is VerificationDecision.PASS else None,
        created_at=NOW,
    )


def test_anchor_pass_alone_is_not_enough_for_default_promotion():
    item = candidate(source_identity_ref=None)
    result = evaluate_evidence_promotion(
        item,
        (verification(VerificationDimension.ANCHOR),),
        EvidencePromotionPolicy("promotion.v0.6"),
    )
    assert result.promotable is False
    assert "MISSING_SOURCE_IDENTITY" in result.reason_codes
    assert VerificationDimension.SOURCE_IDENTITY in result.required_dimensions

    with pytest.raises(EvidencePromotionRejected):
        promote_candidate_evidence(
            item,
            (verification(VerificationDimension.ANCHOR),),
            EvidencePromotionPolicy("promotion.v0.6"),
            created_at=NOW,
        )


def test_anchor_and_source_identity_pass_promote_without_claim_semantic_support():
    item = candidate()
    verifications = (
        verification(VerificationDimension.ANCHOR),
        verification(VerificationDimension.SOURCE_IDENTITY),
    )
    policy = EvidencePromotionPolicy("promotion.v0.6")
    decision = evaluate_evidence_promotion(item, verifications, policy)

    assert decision.promotable is True
    assert decision.required_dimensions == (
        VerificationDimension.ANCHOR,
        VerificationDimension.SOURCE_IDENTITY,
    )
    assert decision.passed_dimensions == decision.required_dimensions

    evidence = promote_candidate_evidence(item, verifications, policy, created_at=NOW)
    assert evidence.status is EvidenceStatus.ANCHORED
    assert evidence.source_identity_ref == "source:a"
    assert evidence.usage_envelope_id == "usage:1"
    assert evidence.verification_refs == (
        "verify:anchor:pass",
        "verify:source_identity:pass",
    )
    assert evidence.metadata["semantic_support_verified"] is False


@pytest.mark.parametrize("bad_decision", [VerificationDecision.FAIL, VerificationDecision.REVIEW])
def test_fail_or_review_on_required_dimension_blocks_promotion(bad_decision):
    verifications = (
        verification(VerificationDimension.ANCHOR),
        verification(VerificationDimension.SOURCE_IDENTITY, bad_decision),
    )
    decision = evaluate_evidence_promotion(
        candidate(),
        verifications,
        EvidencePromotionPolicy("promotion.v0.6"),
    )
    assert decision.promotable is False
    assert any(code.startswith("SOURCE_IDENTITY_") for code in decision.reason_codes)


def test_llm_recall_is_never_promotable_as_external_verified_evidence():
    item = candidate(source_type="llm_recall")
    decision = evaluate_evidence_promotion(
        item,
        (
            verification(VerificationDimension.ANCHOR),
            verification(VerificationDimension.SOURCE_IDENTITY),
        ),
        EvidencePromotionPolicy("promotion.v0.6"),
    )
    assert decision.promotable is False
    assert "LLM_RECALL_NOT_EXTERNAL_EVIDENCE" in decision.reason_codes


def test_optional_fixity_requirement_is_an_additional_gate():
    base = (
        verification(VerificationDimension.ANCHOR),
        verification(VerificationDimension.SOURCE_IDENTITY),
    )
    policy = EvidencePromotionPolicy("promotion.fixity", require_fixity=True)

    missing = evaluate_evidence_promotion(candidate(), base, policy)
    assert missing.promotable is False
    assert "FIXITY_NOT_VERIFIED" in missing.reason_codes

    evidence = promote_candidate_evidence(
        candidate(),
        (*base, verification(VerificationDimension.FIXITY)),
        policy,
        created_at=NOW,
    )
    assert evidence.status is EvidenceStatus.FIXITY_VERIFIED
    assert "verify:fixity:pass" in evidence.verification_refs


def test_promotion_policy_cannot_disable_every_verification_dimension():
    with pytest.raises(ValueError):
        EvidencePromotionPolicy(
            "unsafe",
            require_anchor=False,
            require_source_identity=False,
            require_fixity=False,
        )
