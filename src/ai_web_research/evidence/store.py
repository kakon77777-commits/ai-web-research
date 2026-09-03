from __future__ import annotations

import json

from ai_web_research.storage.trusted_sqlite import TrustedStoreConflict

from .models import (
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


_SCHEMA = """
CREATE TABLE IF NOT EXISTS verification_results (
    verification_id TEXT PRIMARY KEY,
    evidence_ref TEXT NOT NULL,
    claim_ref TEXT,
    dimension TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verified_evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_evidence_id TEXT NOT NULL,
    usage_envelope_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_provenance (
    provenance_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    source_identity_ref TEXT NOT NULL,
    source_family_id TEXT,
    independent_root_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_evidence_relations (
    relation_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verification_results_evidence
ON verification_results(evidence_ref, verification_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_relations_claim
ON claim_evidence_relations(claim_id, relation_id);
"""


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    raise TypeError(type(value).__name__)


def _dump(value) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True)


class EvidenceClosureStore:
    """Additive v0.6 closure persistence over an existing TrustedDataStore.

    The extension owns only verification/promotion/provenance/claim-relation
    tables while sharing the exact same SQLite connection and transaction
    history as the underlying trusted acquisition store.
    """

    def __init__(self, trusted_store) -> None:
        self.trusted_store = trusted_store
        self._conn = trusted_store._conn
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _save_immutable(
        self,
        *,
        table: str,
        id_column: str,
        id_value: str,
        payload: str,
        insert_sql: str,
        params: tuple,
    ) -> None:
        row = self._conn.execute(
            f"SELECT payload_json FROM {table} WHERE {id_column}=?",
            (id_value,),
        ).fetchone()
        if row is not None:
            if row["payload_json"] == payload:
                return
            raise TrustedStoreConflict(
                f"conflicting immutable record {table}:{id_value}"
            )
        self._conn.execute(insert_sql, params)
        self._conn.commit()

    def save_verification_result(self, verification: VerificationResult) -> None:
        payload = _dump(verification)
        self._save_immutable(
            table="verification_results",
            id_column="verification_id",
            id_value=verification.verification_id,
            payload=payload,
            insert_sql="""
                INSERT INTO verification_results
                    (verification_id, evidence_ref, claim_ref, dimension, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """,
            params=(
                verification.verification_id,
                verification.evidence_ref,
                verification.claim_ref,
                verification.dimension.value,
                payload,
            ),
        )

    def get_verification_result(self, verification_id: str) -> VerificationResult:
        row = self._conn.execute(
            "SELECT payload_json FROM verification_results WHERE verification_id=?",
            (verification_id,),
        ).fetchone()
        if row is None:
            raise KeyError(verification_id)
        data = json.loads(row["payload_json"])
        return VerificationResult(
            verification_id=data["verification_id"],
            evidence_ref=data["evidence_ref"],
            claim_ref=data["claim_ref"],
            dimension=VerificationDimension(data["dimension"]),
            decision=VerificationDecision(data["decision"]),
            reason_codes=tuple(data["reason_codes"]),
            verifier_id=data["verifier_id"],
            verifier_version=data["verifier_version"],
            input_refs=tuple(data["input_refs"]),
            output_refs=tuple(data["output_refs"]),
            confidence=data["confidence"],
            created_at=data["created_at"],
        )

    def list_verification_results(
        self, evidence_ref: str | None = None
    ) -> tuple[VerificationResult, ...]:
        if evidence_ref is None:
            rows = self._conn.execute(
                "SELECT verification_id FROM verification_results ORDER BY verification_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT verification_id FROM verification_results
                WHERE evidence_ref=? ORDER BY verification_id
                """,
                (evidence_ref,),
            ).fetchall()
        return tuple(
            self.get_verification_result(row["verification_id"])
            for row in rows
        )

    def save_verified_evidence(self, evidence: VerifiedEvidence) -> None:
        payload = _dump(evidence)
        self._save_immutable(
            table="verified_evidence",
            id_column="evidence_id",
            id_value=evidence.evidence_id,
            payload=payload,
            insert_sql="""
                INSERT INTO verified_evidence
                    (evidence_id, candidate_evidence_id, usage_envelope_id, payload_json)
                VALUES (?, ?, ?, ?)
            """,
            params=(
                evidence.evidence_id,
                evidence.candidate_evidence_id,
                evidence.usage_envelope_id,
                payload,
            ),
        )

    def get_verified_evidence(self, evidence_id: str) -> VerifiedEvidence:
        row = self._conn.execute(
            "SELECT payload_json FROM verified_evidence WHERE evidence_id=?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        data = json.loads(row["payload_json"])
        return VerifiedEvidence(
            evidence_id=data["evidence_id"],
            candidate_evidence_id=data["candidate_evidence_id"],
            acquired_asset_id=data["acquired_asset_id"],
            source_identity_ref=data["source_identity_ref"],
            work_identity_ref=data["work_identity_ref"],
            version_identity_ref=data["version_identity_ref"],
            manifestation_identity_ref=data["manifestation_identity_ref"],
            anchor_refs=tuple(data["anchor_refs"]),
            verification_refs=tuple(data["verification_refs"]),
            usage_envelope_id=data["usage_envelope_id"],
            status=EvidenceStatus(data["status"]),
            created_at=data["created_at"],
            metadata=data["metadata"],
        )

    def save_evidence_provenance(self, provenance: EvidenceProvenance) -> None:
        payload = _dump(provenance)
        self._save_immutable(
            table="evidence_provenance",
            id_column="provenance_id",
            id_value=provenance.provenance_id,
            payload=payload,
            insert_sql="""
                INSERT INTO evidence_provenance
                    (provenance_id, evidence_id, source_identity_ref,
                     source_family_id, independent_root_ref, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
            params=(
                provenance.provenance_id,
                provenance.evidence_id,
                provenance.source_identity_ref,
                provenance.source_family_id,
                provenance.independent_root_ref,
                payload,
            ),
        )

    def get_evidence_provenance(self, provenance_id: str) -> EvidenceProvenance:
        row = self._conn.execute(
            "SELECT payload_json FROM evidence_provenance WHERE provenance_id=?",
            (provenance_id,),
        ).fetchone()
        if row is None:
            raise KeyError(provenance_id)
        data = json.loads(row["payload_json"])
        return EvidenceProvenance(
            provenance_id=data["provenance_id"],
            evidence_id=data["evidence_id"],
            source_identity_ref=data["source_identity_ref"],
            source_family_id=data["source_family_id"],
            independent_root_ref=data["independent_root_ref"],
            root_resolved=data["root_resolved"],
            lineage_relation_refs=tuple(data["lineage_relation_refs"]),
            created_at=data["created_at"],
        )

    def save_claim_evidence_relation(
        self, relation: ClaimEvidenceRelation
    ) -> None:
        payload = _dump(relation)
        self._save_immutable(
            table="claim_evidence_relations",
            id_column="relation_id",
            id_value=relation.relation_id,
            payload=payload,
            insert_sql="""
                INSERT INTO claim_evidence_relations
                    (relation_id, claim_id, evidence_id, relation_type, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """,
            params=(
                relation.relation_id,
                relation.claim_id,
                relation.evidence_id,
                relation.relation_type.value,
                payload,
            ),
        )

    def get_claim_evidence_relation(
        self, relation_id: str
    ) -> ClaimEvidenceRelation:
        row = self._conn.execute(
            """
            SELECT payload_json FROM claim_evidence_relations
            WHERE relation_id=?
            """,
            (relation_id,),
        ).fetchone()
        if row is None:
            raise KeyError(relation_id)
        data = json.loads(row["payload_json"])
        return ClaimEvidenceRelation(
            relation_id=data["relation_id"],
            claim_id=data["claim_id"],
            evidence_id=data["evidence_id"],
            relation_type=ClaimEvidenceRelationType(data["relation_type"]),
            semantic_verification_ref=data["semantic_verification_ref"],
            provenance_ref=data["provenance_ref"],
            confidence=data["confidence"],
            created_at=data["created_at"],
        )

    def list_claim_evidence_relations(
        self, claim_id: str
    ) -> tuple[ClaimEvidenceRelation, ...]:
        rows = self._conn.execute(
            """
            SELECT relation_id FROM claim_evidence_relations
            WHERE claim_id=? ORDER BY relation_id
            """,
            (claim_id,),
        ).fetchall()
        return tuple(
            self.get_claim_evidence_relation(row["relation_id"])
            for row in rows
        )
