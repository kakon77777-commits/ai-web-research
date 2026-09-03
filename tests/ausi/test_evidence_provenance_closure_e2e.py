from dataclasses import replace

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.evidence.closure import (
    EvidencePromotionPolicy,
    EvidencePromotionRejected,
    promote_candidate_evidence,
)
from ai_web_research.evidence.materialize import materialize_candidate_evidence
from ai_web_research.evidence.models import (
    AcquiredAsset,
    ClaimEvidenceRelationType,
    EvidenceStatus,
    MaterializedAsset,
)
from ai_web_research.evidence.runtime import EvidenceClosureRuntime
from ai_web_research.evidence.verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)
from ai_web_research.gaps.projection import EvidenceGapType
from ai_web_research.policy.models import AcquisitionAction, UsageEnvelope
from ai_web_research.source_graph.family import resolve_source_families
from ai_web_research.source_graph.models import (
    RelationInferenceType,
    SourceNode,
    SourceRelation,
    SourceRelationType,
)
from ai_web_research.storage.trusted_sqlite import TrustedDataStore


NOW = "2026-09-03T09:40:00+00:00"


def envelope(asset_id: str):
    return UsageEnvelope(
        envelope_id=f"{asset_id}:usage",
        asset_ref=asset_id,
        permissions=(AcquisitionAction.INTERNAL_USE,),
        prohibitions=(),
        obligations=(),
        limits=(),
        source_policy_refs=("policy.example@1.0.0",),
        inherited_from=(),
        created_at=NOW,
        evaluator_version="ausi-policy/0.1.0",
        metadata={},
    )


def extracted(asset_id: str, value: str = "42"):
    artifact = ArtifactRef(
        ArtifactKind.EVIDENCE_CANDIDATE,
        f"{asset_id}:extract",
        metadata={
            "extractor_version": "extractor/1",
            "model": "model-x",
            "fields": {
                "answer": {
                    "value": value,
                    "source_quote": f"answer is {value}",
                    "confidence": 0.9,
                    "quote_verified": True,
                }
            },
            "validation_errors": [],
            "source_type": "web_crawled_extraction",
        },
    )
    materialized = MaterializedAsset(
        asset=AcquiredAsset(
            asset_id=asset_id,
            observation_id=f"{asset_id}:obs",
            provider_id="provider.crawler",
            surface_id="surface.crawler.browser",
            artifact_ref=artifact,
            raw_ref=f"raw/{asset_id}.html",
            media_type="text/html",
            retrieved_at=NOW,
            content_hash=f"hash:{asset_id}",
            usage_envelope_id=f"{asset_id}:usage",
            acquisition_event_id=f"{asset_id}:acquired",
            metadata={},
        ),
        usage_envelope=envelope(asset_id),
    )
    bundle = materialize_candidate_evidence(materialized)
    assert len(bundle.candidates) == 1
    assert bundle.verifications[0].dimension is VerificationDimension.ANCHOR
    assert bundle.verifications[0].decision is VerificationDecision.PASS
    return materialized, bundle


def source(source_id: str, date: str):
    return SourceNode(
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        canonical_url=None,
        published_at=date,
        observed_at=NOW,
        owner_hint=None,
        content_hash=f"hash:{source_id}",
        metadata={},
    )


def source_verification(candidate_id: str):
    return VerificationResult(
        verification_id=f"{candidate_id}:source-identity",
        evidence_ref=candidate_id,
        claim_ref=None,
        dimension=VerificationDimension.SOURCE_IDENTITY,
        decision=VerificationDecision.PASS,
        reason_codes=("SOURCE_IDENTITY_VERIFIED",),
        verifier_id="source.identity.verifier",
        verifier_version="1.0",
        input_refs=(candidate_id,),
        output_refs=(),
        confidence=1.0,
        created_at=NOW,
    )


def semantic(evidence_id: str, claim_id: str):
    return VerificationResult(
        verification_id=f"{evidence_id}:semantic:{claim_id}",
        evidence_ref=evidence_id,
        claim_ref=claim_id,
        dimension=VerificationDimension.SEMANTIC_SUPPORT,
        decision=VerificationDecision.PASS,
        reason_codes=("SEMANTIC_RELATION_VERIFIED",),
        verifier_id="semantic.verifier",
        verifier_version="1.0",
        input_refs=(evidence_id, claim_id),
        output_refs=(),
        confidence=0.92,
        created_at=NOW,
    )


def test_v06_closes_candidate_to_provenance_claim_relation_and_independence(tmp_path):
    # Provider-grounded/search output remains discovery-only and cannot promote.
    discovery = DiscoveryCandidate(
        candidate_id="search:1",
        url="https://example.com/search-hit",
        title="Search hit",
        snippet="answer is 42",
        provider_id="provider.gemini_google",
        surface_id="surface.gemini.google_search",
        provider_rank=1,
        artifact_ids=("artifact:search:1",),
        metadata={"model_native": True, "evidence_role": "discovery_only"},
    )
    with pytest.raises(EvidencePromotionRejected) as exc:
        promote_candidate_evidence(
            discovery,
            (),
            EvidencePromotionPolicy("promotion.v0.6"),
            created_at=NOW,
        )
    assert "NOT_CANDIDATE_EVIDENCE" in exc.value.decision.reason_codes

    nodes = (
        source("source:a", "2026-01-01"),
        source("source:a-mirror", "2026-01-02"),
        source("source:b", "2026-01-03"),
        source("source:c", "2026-01-04"),
        source("source:anchor-only", "2026-01-05"),
    )
    mirror = SourceRelation(
        relation_id="rel:mirror",
        from_source_id="source:a-mirror",
        to_source_id="source:a",
        relation_type=SourceRelationType.MIRRORS,
        confidence=1.0,
        inference_type=RelationInferenceType.EXPLICIT,
        signals=("explicit-mirror",),
    )
    families = resolve_source_families(nodes, (mirror,))

    store = TrustedDataStore(tmp_path / "trusted.db")
    runtime = EvidenceClosureRuntime(store)
    try:
        # Quote/anchor PASS can become promoted evidence once source identity is
        # independently verified, but without SEMANTIC_SUPPORT it cannot link
        # to a claim.
        materialized_anchor, anchor_bundle = extracted("asset:anchor-only")
        store.save_usage_envelope(materialized_anchor.usage_envelope)
        anchor_candidate = replace(
            anchor_bundle.candidates[0],
            source_identity_ref="source:anchor-only",
        )
        anchor_verifications = (
            *anchor_bundle.verifications,
            source_verification(anchor_candidate.candidate_evidence_id),
        )
        anchor_only = runtime.close(
            anchor_candidate,
            anchor_verifications,
            families,
            source_relations=(mirror,),
            claim_id="claim:anchor-only",
            relation_type=ClaimEvidenceRelationType.SUPPORTS,
            semantic_verification=None,
            created_at=NOW,
        )
        assert anchor_only.evidence.status is EvidenceStatus.ANCHORED
        assert anchor_only.claim_relation is None
        assert EvidenceGapType.UNVERIFIED_SEMANTIC_SUPPORT in anchor_only.gap_projection.gap_types

        closure_results = {}
        for asset_id, source_id, rel_type, value in (
            ("asset:a", "source:a", ClaimEvidenceRelationType.SUPPORTS, "42"),
            ("asset:mirror", "source:a-mirror", ClaimEvidenceRelationType.SUPPORTS, "42"),
            ("asset:b", "source:b", ClaimEvidenceRelationType.SUPPORTS, "42"),
            ("asset:c", "source:c", ClaimEvidenceRelationType.CONTRADICTS, "41"),
        ):
            materialized, bundle = extracted(asset_id, value)
            store.save_usage_envelope(materialized.usage_envelope)
            item = replace(bundle.candidates[0], source_identity_ref=source_id)
            ev_id = f"{item.candidate_evidence_id}:verified"
            result = runtime.close(
                item,
                (*bundle.verifications, source_verification(item.candidate_evidence_id)),
                families,
                source_relations=(mirror,),
                claim_id="claim:1",
                relation_type=rel_type,
                semantic_verification=semantic(ev_id, "claim:1"),
                created_at=NOW,
            )
            closure_results[asset_id] = result

        a = closure_results["asset:a"]
        mirror_result = closure_results["asset:mirror"]
        b = closure_results["asset:b"]
        c = closure_results["asset:c"]

        assert a.claim_relation is not None
        assert a.claim_relation.relation_type is ClaimEvidenceRelationType.SUPPORTS
        assert a.evidence.usage_envelope_id == "asset:a:usage"

        # a + mirror are the same origin family, so still only one independent root.
        assert mirror_result.claim_assessment.independent_support_root_count == 1
        assert mirror_result.claim_assessment.status is EvidenceStatus.CLAIM_LINKED
        assert a.provenance.independent_root_ref == mirror_result.provenance.independent_root_ref

        # A genuinely independent source raises support to two roots.
        assert b.claim_assessment.independent_support_root_count == 2
        assert b.claim_assessment.status is EvidenceStatus.CORROBORATED

        # A semantically verified contradiction makes the claim contested.
        assert c.claim_assessment.status is EvidenceStatus.CONTESTED
        assert c.claim_assessment.independent_contradiction_root_count == 1
        assert EvidenceGapType.UNRESOLVED_CONTRADICTION in c.gap_projection.gap_types

        # Closure identities and policy lineage survive persistence/reload.
        loaded_evidence = runtime.closure_store.get_verified_evidence(
            a.evidence.evidence_id
        )
        loaded_provenance = runtime.closure_store.get_evidence_provenance(
            a.provenance.provenance_id
        )
        assert loaded_evidence.usage_envelope_id == "asset:a:usage"
        assert loaded_provenance.independent_root_ref == "source:a"

        events = store.list_ledger_events()
        event_types = [event.event_type for event in events]
        assert "VERIFICATION_RECORDED" in event_types
        assert "EVIDENCE_PROMOTED" in event_types
        assert "PROVENANCE_ATTACHED" in event_types
        assert "CLAIM_EVIDENCE_LINKED" in event_types
        assert "CLAIM_CORROBORATED" in event_types
        assert "CLAIM_CONTESTED" in event_types

        # Ledger is append-only: closure added history, not an update API.
        assert not hasattr(runtime.ledger, "update")
        sequences = [event.sequence for event in events]
        assert sequences == sorted(sequences)
        assert len(sequences) == len(set(sequences))
    finally:
        store.close()


def test_closure_runtime_rejects_source_identity_disabled_policy_before_side_effects(tmp_path):
    materialized, bundle = extracted("asset:unsafe-policy")
    store = TrustedDataStore(tmp_path / "trusted.db")
    store.save_usage_envelope(materialized.usage_envelope)
    runtime = EvidenceClosureRuntime(store)
    families = resolve_source_families(
        (source("source:unsafe", "2026-01-01"),),
        (),
    )
    try:
        with pytest.raises(ValueError, match="source identity"):
            runtime.close(
                bundle.candidates[0],
                bundle.verifications,
                families,
                promotion_policy=EvidencePromotionPolicy(
                    "unsafe-for-closure",
                    require_anchor=True,
                    require_source_identity=False,
                ),
                created_at=NOW,
            )
        assert store.list_ledger_events() == ()
    finally:
        store.close()
