from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.evidence.anchors import AnchorKind, EvidenceAnchor
from ai_web_research.evidence.ledger import EvidenceLedger
from ai_web_research.evidence.models import AcquiredAsset, CandidateEvidence
from ai_web_research.evidence.verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)
from ai_web_research.gaps.projection import EvidenceGapType, project_candidate_gaps
from ai_web_research.policy.models import (
    AcquisitionAction,
    PolicyRule,
    PolicyRuleEffect,
    PolicySourceRef,
    SourcePolicyProfile,
    UsageEnvelope,
)
from ai_web_research.storage.trusted_sqlite import TrustedDataStore, TrustedStoreConflict


def make_policy():
    return SourcePolicyProfile(
        policy_id="policy.example",
        version="1.0.0",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        asset_scope="*",
        rules=(
            PolicyRule(
                rule_id="allow",
                action=AcquisitionAction.FETCH,
                effect=PolicyRuleEffect.PERMISSION,
                value=True,
                asset_scope="*",
                party_scope=None,
                purpose_scope=("research",),
                constraints={},
                source_refs=("source1",),
                priority_hint=1,
            ),
        ),
        policy_sources=(
            PolicySourceRef(
                source_id="source1",
                uri="https://example.com/terms",
                title="Terms",
                retrieved_at="2026-08-31T00:00:00+00:00",
                effective_at=None,
                expires_at=None,
                content_hash="phash",
                anchor={},
                authority="provider",
                interpretation_status="human_verified",
            ),
        ),
        auth_requirements={},
        rate_limits={},
        retention_rules={},
        attribution_rules={},
        redistribution_rules={},
        privacy_flags=(),
        observed_at="2026-08-31T00:00:00+00:00",
        effective_at=None,
        expires_at=None,
        next_review_at=None,
        policy_hash="policyhash",
        review_status="verified",
        metadata={},
    )


def make_envelope():
    return UsageEnvelope(
        envelope_id="usage1",
        asset_ref="asset1",
        permissions=(AcquisitionAction.FETCH, AcquisitionAction.INTERNAL_USE),
        prohibitions=(),
        obligations=(),
        limits=(),
        source_policy_refs=("policy.example@1.0.0",),
        inherited_from=(),
        created_at="2026-08-31T12:00:00+00:00",
        evaluator_version="ausi-policy/0.1.0",
        metadata={},
    )


def make_asset():
    return AcquiredAsset(
        asset_id="asset1",
        observation_id="obs1",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        artifact_ref=ArtifactRef(
            ArtifactKind.EVIDENCE_CANDIDATE,
            "extract1",
            metadata={"source_type": "web_crawled_extraction"},
        ),
        raw_ref="raw/a.html",
        media_type="text/html",
        retrieved_at="2026-08-31T12:00:00+00:00",
        content_hash="hash1",
        usage_envelope_id="usage1",
        acquisition_event_id="event-acq-1",
        metadata={},
    )


def make_anchor():
    return EvidenceAnchor(
        anchor_id="anchor1",
        kind=AnchorKind.TEXT_SPAN,
        manifestation_id=None,
        locator={"source_quote": "quote"},
        anchored_text="quote",
        anchored_hash="qhash",
        created_at="2026-08-31T12:00:00+00:00",
        metadata={},
    )


def make_candidate():
    return CandidateEvidence(
        candidate_evidence_id="candidate1",
        acquired_asset_id="asset1",
        field_name="answer",
        extracted_value="42",
        source_identity_ref=None,
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=("anchor1",),
        extraction_method="method.extract_candidate_evidence",
        extractor_version="extractor/1",
        model_ref="model-x",
        source_type="web_crawled_extraction",
        usage_envelope_id="usage1",
        extractor_confidence=0.9,
        semantic_support_verified=False,
        validation_notes=(),
        created_at="2026-08-31T12:00:00+00:00",
    )


def test_trusted_store_persists_core_wp03_records(tmp_path):
    store = TrustedDataStore(tmp_path / "trusted.db")
    try:
        store.save_policy_profile(make_policy())
        store.save_usage_envelope(make_envelope())
        store.save_acquired_asset(make_asset())
        store.save_anchor(make_anchor())
        store.save_candidate_evidence(make_candidate())

        assert store.get_policy_profile_payload("policy.example", "1.0.0")["provider_id"] == "provider.crawler"
        assert store.get_usage_envelope("usage1").permissions[0] is AcquisitionAction.FETCH
        assert store.get_acquired_asset("asset1").artifact_ref.id == "extract1"
        assert store.get_anchor("anchor1").anchored_text == "quote"
        assert store.get_candidate_evidence("candidate1").field_name == "answer"
    finally:
        store.close()


def test_evidence_ledger_is_append_only_and_monotonic(tmp_path):
    store = TrustedDataStore(tmp_path / "trusted.db")
    ledger = EvidenceLedger(store)
    try:
        first = ledger.append(
            event_id="event1",
            event_type="ASSET_ACQUIRED",
            subject_type="asset",
            subject_id="asset1",
            actor_id="runtime",
            actor_version="0.1",
            input_refs=(),
            output_refs=("asset1",),
            payload={},
            created_at="2026-08-31T12:00:00+00:00",
        )
        second = ledger.append(
            event_id="event2",
            event_type="EVIDENCE_CANDIDATE_CREATED",
            subject_type="candidate_evidence",
            subject_id="candidate1",
            actor_id="runtime",
            actor_version="0.1",
            input_refs=("asset1",),
            output_refs=("candidate1",),
            payload={},
            created_at="2026-08-31T12:00:01+00:00",
        )
        assert (first.sequence, second.sequence) == (1, 2)
        assert [e.event_id for e in ledger.list_events()] == ["event1", "event2"]
        assert not hasattr(ledger, "update")
    finally:
        store.close()


def test_gap_projection_from_anchor_failure_missing_identity_and_policy_restriction(tmp_path):
    candidate = make_candidate()
    failed_anchor = VerificationResult(
        verification_id="v1",
        evidence_ref="candidate1",
        claim_ref=None,
        dimension=VerificationDimension.ANCHOR,
        decision=VerificationDecision.FAIL,
        reason_codes=("ANCHOR_NOT_VERIFIED",),
        verifier_id="legacy.quote_verifier",
        verifier_version="1",
        input_refs=("asset1",),
        output_refs=("anchor1",),
        confidence=None,
        created_at="2026-08-31T12:00:00+00:00",
    )
    projection = project_candidate_gaps(
        candidate,
        (failed_anchor,),
        policy_restricted=True,
        require_source_identity=True,
        require_version=True,
        created_at="2026-08-31T12:00:01+00:00",
    )
    assert EvidenceGapType.UNVERIFIED_ANCHOR in projection.gap_types
    assert EvidenceGapType.MISSING_IDENTITY in projection.gap_types
    assert EvidenceGapType.MISSING_VERSION in projection.gap_types
    assert EvidenceGapType.POLICY_RESTRICTED_SOURCE in projection.gap_types

    store = TrustedDataStore(tmp_path / "trusted.db")
    try:
        store.save_gap_projection(projection)
        loaded = store.get_gap_projection(projection.gap_projection_id)
        assert loaded.gap_types == projection.gap_types
    finally:
        store.close()


def test_policy_store_rejects_same_version_payload_conflict(tmp_path):
    store = TrustedDataStore(tmp_path / "trusted.db")
    try:
        original = make_policy()
        store.save_policy_profile(original)
        conflicting = SourcePolicyProfile(
            **{
                **original.__dict__,
                "policy_hash": "different-hash",
                "metadata": {"changed": True},
            }
        )
        try:
            store.save_policy_profile(conflicting)
        except TrustedStoreConflict:
            pass
        else:
            raise AssertionError("same policy id/version must not be silently replaced")
    finally:
        store.close()
