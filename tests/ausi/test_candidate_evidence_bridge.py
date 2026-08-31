from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.evidence.materialize import materialize_candidate_evidence
from ai_web_research.evidence.verifier import VerificationDecision, VerificationDimension
from ai_web_research.policy.models import AcquisitionAction, UsageEnvelope
from ai_web_research.evidence.models import AcquiredAsset, MaterializedAsset


def make_materialized(fields):
    artifact = ArtifactRef(
        ArtifactKind.EVIDENCE_CANDIDATE,
        "extract:1",
        metadata={
            "document_id": "doc1",
            "url": "https://example.com/a",
            "extractor_version": "extractor/1",
            "provider": "vertex",
            "model": "model-x",
            "fields": fields,
            "validation_errors": [],
            "source_type": "web_crawled_extraction",
            "verification_scope": "anchor_only",
            "semantic_support_verified": False,
        },
    )
    envelope = UsageEnvelope(
        envelope_id="usage1",
        asset_ref="asset1",
        permissions=(AcquisitionAction.INTERNAL_USE,),
        prohibitions=(),
        obligations=(),
        limits=(),
        source_policy_refs=("policy.example@1.0.0",),
        inherited_from=(),
        created_at="2026-08-31T12:00:00+00:00",
        evaluator_version="ausi-policy/0.1.0",
        metadata={},
    )
    asset = AcquiredAsset(
        asset_id="asset1",
        observation_id="obs1",
        provider_id="provider.llm_recall",
        surface_id="surface.llm.vertex",
        artifact_ref=artifact,
        raw_ref="storage/raw/a.html",
        media_type="text/markdown",
        retrieved_at="2026-08-31T12:00:00+00:00",
        content_hash="hash1",
        usage_envelope_id="usage1",
        acquisition_event_id="a1:acquired:1",
        metadata={},
    )
    return MaterializedAsset(asset, envelope)


def test_extraction_fields_become_independent_candidate_evidence_records():
    materialized = make_materialized({
        "answer": {
            "value": "42",
            "source_quote": "the answer is 42",
            "confidence": 0.9,
            "quote_verified": True,
        },
        "unit": {
            "value": "widgets",
            "source_quote": "42 widgets",
            "confidence": 0.8,
            "quote_verified": True,
        },
    })
    result = materialize_candidate_evidence(materialized)
    assert len(result.candidates) == 2
    assert [c.field_name for c in result.candidates] == ["answer", "unit"]
    assert all(c.semantic_support_verified is False for c in result.candidates)


def test_source_quote_creates_text_anchor_and_quote_verified_only_passes_anchor_dimension():
    materialized = make_materialized({
        "answer": {
            "value": "42",
            "source_quote": "the answer is 42",
            "confidence": 0.9,
            "quote_verified": True,
        }
    })
    result = materialize_candidate_evidence(materialized)
    assert len(result.anchors) == 1
    assert result.anchors[0].anchored_text == "the answer is 42"
    assert len(result.verifications) == 1
    verification = result.verifications[0]
    assert verification.dimension is VerificationDimension.ANCHOR
    assert verification.decision is VerificationDecision.PASS
    assert not any(v.dimension is VerificationDimension.SEMANTIC_SUPPORT for v in result.verifications)


def test_unverified_or_missing_quote_is_anchor_failure_and_gap_hint():
    materialized = make_materialized({
        "bad": {
            "value": "x",
            "source_quote": "not actually present",
            "confidence": 0.7,
            "quote_verified": False,
        },
        "missing": {
            "value": "y",
            "source_quote": None,
            "confidence": 0.4,
            "quote_verified": False,
        },
    })
    result = materialize_candidate_evidence(materialized)
    assert [v.decision for v in result.verifications] == [
        VerificationDecision.FAIL,
        VerificationDecision.FAIL,
    ]
    assert "unverified_anchor" in result.gap_hints


def test_non_extraction_artifact_and_llm_recall_do_not_materialize_external_candidate_evidence():
    envelope = UsageEnvelope(
        envelope_id="usage2",
        asset_ref="asset2",
        permissions=(AcquisitionAction.INTERNAL_USE,),
        prohibitions=(),
        obligations=(),
        limits=(),
        source_policy_refs=(),
        inherited_from=(),
        created_at="2026-08-31T12:00:00+00:00",
        evaluator_version="ausi-policy/0.1.0",
        metadata={},
    )
    artifact = ArtifactRef(
        ArtifactKind.CANDIDATE,
        "recall1",
        metadata={"source_type": "llm_recall", "external_evidence": False},
    )
    asset = AcquiredAsset(
        asset_id="asset2",
        observation_id="obs2",
        provider_id="provider.llm_recall",
        surface_id="surface.llm.vertex",
        artifact_ref=artifact,
        raw_ref=None,
        media_type=None,
        retrieved_at="2026-08-31T12:00:00+00:00",
        content_hash=None,
        usage_envelope_id="usage2",
        acquisition_event_id="a2:acquired:1",
        metadata={},
    )
    result = materialize_candidate_evidence(MaterializedAsset(asset, envelope))
    assert result.candidates == ()
    assert result.anchors == ()
    assert result.verifications == ()
