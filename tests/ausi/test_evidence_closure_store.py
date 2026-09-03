import sqlite3

import pytest

from ai_web_research.evidence.models import (
    ClaimEvidenceRelation,
    ClaimEvidenceRelationType,
    EvidenceProvenance,
    EvidenceStatus,
    VerifiedEvidence,
)
from ai_web_research.evidence.verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)
from ai_web_research.evidence.store import EvidenceClosureStore
from ai_web_research.storage.trusted_sqlite import TrustedDataStore, TrustedStoreConflict


NOW = "2026-09-03T09:30:00+00:00"


def verification(**overrides):
    values = dict(
        verification_id="verify:1",
        evidence_ref="candidate:1",
        claim_ref=None,
        dimension=VerificationDimension.ANCHOR,
        decision=VerificationDecision.PASS,
        reason_codes=("ANCHOR_VERIFIED",),
        verifier_id="anchor.verifier",
        verifier_version="1.0",
        input_refs=("asset:1",),
        output_refs=("anchor:1",),
        confidence=1.0,
        created_at=NOW,
    )
    values.update(overrides)
    return VerificationResult(**values)


def evidence(**overrides):
    values = dict(
        evidence_id="evidence:1",
        candidate_evidence_id="candidate:1",
        acquired_asset_id="asset:1",
        source_identity_ref="source:a",
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=("anchor:1",),
        verification_refs=("verify:1", "verify:source"),
        usage_envelope_id="usage:1",
        status=EvidenceStatus.ANCHORED,
        created_at=NOW,
        metadata={"promotion_policy_id": "promotion.v0.6"},
    )
    values.update(overrides)
    return VerifiedEvidence(**values)


def provenance(**overrides):
    values = dict(
        provenance_id="provenance:1",
        evidence_id="evidence:1",
        source_identity_ref="source:a",
        source_family_id="family:a",
        independent_root_ref="source:a",
        root_resolved=True,
        lineage_relation_refs=("source-rel:1",),
        created_at=NOW,
    )
    values.update(overrides)
    return EvidenceProvenance(**values)


def relation(**overrides):
    values = dict(
        relation_id="claim-rel:1",
        claim_id="claim:1",
        evidence_id="evidence:1",
        relation_type=ClaimEvidenceRelationType.SUPPORTS,
        semantic_verification_ref="verify:semantic:1",
        provenance_ref="provenance:1",
        confidence=0.9,
        created_at=NOW,
    )
    values.update(overrides)
    return ClaimEvidenceRelation(**values)


def test_store_roundtrips_v06_closure_records_and_lists_claim_relations(tmp_path):
    trusted = TrustedDataStore(tmp_path / "trusted.db")
    store = EvidenceClosureStore(trusted)
    try:
        v = verification()
        e = evidence()
        p = provenance()
        r = relation()
        store.save_verification_result(v)
        store.save_verified_evidence(e)
        store.save_evidence_provenance(p)
        store.save_claim_evidence_relation(r)

        assert store.get_verification_result("verify:1") == v
        assert store.get_verified_evidence("evidence:1") == e
        assert store.get_evidence_provenance("provenance:1") == p
        assert store.get_claim_evidence_relation("claim-rel:1") == r
        assert store.list_claim_evidence_relations("claim:1") == (r,)
    finally:
        trusted.close()


@pytest.mark.parametrize(
    ("save_name", "original", "conflicting"),
    [
        (
            "save_verification_result",
            verification(),
            verification(reason_codes=("DIFFERENT",)),
        ),
        (
            "save_verified_evidence",
            evidence(),
            evidence(metadata={"changed": True}),
        ),
        (
            "save_evidence_provenance",
            provenance(),
            provenance(independent_root_ref="source:other"),
        ),
        (
            "save_claim_evidence_relation",
            relation(),
            relation(confidence=0.1),
        ),
    ],
)
def test_closure_records_are_idempotent_for_same_payload_and_conflict_safe(
    tmp_path, save_name, original, conflicting
):
    trusted = TrustedDataStore(tmp_path / "trusted.db")
    store = EvidenceClosureStore(trusted)
    try:
        save = getattr(store, save_name)
        save(original)
        save(original)
        with pytest.raises(TrustedStoreConflict):
            save(conflicting)
    finally:
        trusted.close()


def test_additive_schema_keeps_preexisting_tables_untouched(tmp_path):
    db = tmp_path / "trusted.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE legacy_marker (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO legacy_marker VALUES ('legacy-1', 'still-here')")
    conn.commit()
    conn.close()

    trusted = TrustedDataStore(db)
    store = EvidenceClosureStore(trusted)
    try:
        row = trusted._conn.execute(
            "SELECT value FROM legacy_marker WHERE id='legacy-1'"
        ).fetchone()
        assert row["value"] == "still-here"
        store.save_verification_result(verification())
        assert store.get_verification_result("verify:1").decision is VerificationDecision.PASS
    finally:
        trusted.close()
