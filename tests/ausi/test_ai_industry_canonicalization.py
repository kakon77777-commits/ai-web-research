import pytest

from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.knowledge.models import ClaimOrigin, ClaimState, EventStatus, ValidTime
from ai_web_research.domains.ai_industry.models import (
    AIEntityType,
    AIEventType,
    AIIndustryEntity,
    ClaimDraft,
    EventDraft,
)
from ai_web_research.domains.ai_industry.canonicalize import canonicalize_event, promote_claim


def _evidence(evidence_id: str) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_evidence_id=evidence_id,
        acquired_asset_id=f"asset:{evidence_id}",
        field_name="key_claim",
        extracted_value="Model X was released.",
        source_identity_ref="source:official",
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=(f"anchor:{evidence_id}",),
        extraction_method="fixture",
        extractor_version="fixture-v1",
        model_ref=None,
        source_type="primary_official",
        usage_envelope_id="usage:1",
        extractor_confidence=1.0,
        semantic_support_verified=False,
        validation_notes=(),
        created_at="2026-08-31T09:05:00Z",
    )


def test_ai_entity_contract_distinguishes_model_from_product():
    model = AIIndustryEntity(
        entity_id="model:model-x",
        entity_type=AIEntityType.MODEL_VERSION,
        canonical_name="Model X",
        aliases=("X",),
        external_ids={"repo": "org/model-x"},
        status="active",
    )
    product = AIIndustryEntity(
        entity_id="product:assistant-x",
        entity_type=AIEntityType.PRODUCT,
        canonical_name="Assistant X",
        aliases=(),
        external_ids={},
        status="active",
    )

    assert model.entity_type is AIEntityType.MODEL_VERSION
    assert product.entity_type is AIEntityType.PRODUCT
    assert model.entity_id != product.entity_id


def test_promote_source_assertion_requires_evidence():
    draft = ClaimDraft(
        claim_id="claim:no-evidence",
        statement="Model X was released.",
        subject_id="model:model-x",
        predicate="released",
        object_value=True,
        state=ClaimState.CONFIRMED,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence=(),
        independent_root_count=0,
        known_at="2026-08-31T09:05:00Z",
        valid_time=ValidTime(start="2026-08-31T09:00:00Z"),
        metadata={},
    )

    with pytest.raises(ValueError, match="source assertion requires evidence"):
        promote_claim(draft)


def test_promote_derived_inference_can_be_explicitly_evidence_free():
    draft = ClaimDraft(
        claim_id="claim:derived",
        statement="Company A and Company B have market overlap.",
        subject_id="org:a",
        predicate="market_overlap",
        object_value="org:b",
        state=ClaimState.WELL_SUPPORTED,
        claim_origin=ClaimOrigin.DERIVED_INFERENCE,
        evidence=(),
        independent_root_count=0,
        known_at="2026-08-31T09:05:00Z",
        valid_time=None,
        metadata={"inference_method": "overlap_v1"},
    )

    claim = promote_claim(draft)
    assert claim.claim_origin is ClaimOrigin.DERIVED_INFERENCE
    assert claim.evidence_ids == ()


def test_promote_claim_preserves_independent_root_count_and_deduplicates_evidence():
    e1 = _evidence("ev:blog")
    e2 = _evidence("ev:repo")
    draft = ClaimDraft(
        claim_id="claim:model-x-release",
        statement="Model X was released.",
        subject_id="model:model-x",
        predicate="released",
        object_value=True,
        state=ClaimState.CONFIRMED,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence=(e1, e2, e1),
        independent_root_count=2,
        known_at="2026-08-31T09:05:00Z",
        valid_time=ValidTime(start="2026-08-31T09:00:00Z"),
        metadata={},
    )

    claim = promote_claim(draft)
    assert claim.revision == 1
    assert claim.evidence_ids == ("ev:blog", "ev:repo")
    assert claim.independent_root_count == 2


def test_canonicalize_event_uses_explicit_stable_id_and_order_preserving_dedup():
    draft = EventDraft(
        event_id="evt:model-x-release",
        event_type=AIEventType.MODEL_RELEASE,
        entity_ids=("model:model-x", "org:company-y", "model:model-x"),
        status=EventStatus.CONFIRMED,
        claim_ids=("claim:model-x-release", "claim:model-x-release"),
        evidence_ids=("ev:blog", "ev:repo", "ev:blog"),
        known_at="2026-08-31T09:05:00Z",
        valid_time=ValidTime(start="2026-08-31T09:00:00Z"),
        metadata={"importance": 0.95},
    )

    event = canonicalize_event(draft)
    assert event.event_id == "evt:model-x-release"
    assert event.revision == 1
    assert event.event_type == AIEventType.MODEL_RELEASE.value
    assert event.entity_ids == ("model:model-x", "org:company-y")
    assert event.claim_ids == ("claim:model-x-release",)
    assert event.evidence_ids == ("ev:blog", "ev:repo")
