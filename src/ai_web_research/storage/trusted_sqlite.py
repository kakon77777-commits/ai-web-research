from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.evidence.anchors import AnchorKind, EvidenceAnchor
from ai_web_research.evidence.ledger import EvidenceLedgerEvent
from ai_web_research.evidence.models import AcquiredAsset, CandidateEvidence
from ai_web_research.gaps.projection import EvidenceGapType, GapProjection
from ai_web_research.policy.models import (
    AcquisitionAction,
    Obligation,
    PolicyLimit,
    SourcePolicyProfile,
    UsageEnvelope,
)


class TrustedStoreConflict(ValueError):
    pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_profiles (
    policy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    surface_id TEXT NOT NULL,
    policy_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (policy_id, version)
);
CREATE TABLE IF NOT EXISTS usage_envelopes (
    envelope_id TEXT PRIMARY KEY,
    asset_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acquired_assets (
    asset_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    surface_id TEXT NOT NULL,
    usage_envelope_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_anchors (
    anchor_id TEXT PRIMARY KEY,
    anchor_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_evidence (
    candidate_evidence_id TEXT PRIMARY KEY,
    acquired_asset_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    usage_envelope_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_ledger_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gap_projections (
    gap_projection_id TEXT PRIMARY KEY,
    claim_id TEXT,
    payload_json TEXT NOT NULL
);
"""


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _canonical(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


def _dump(value) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True)


class TrustedDataStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_policy_profile(self, profile: SourcePolicyProfile) -> None:
        payload = _dump(profile)
        existing = self._conn.execute(
            """
            SELECT provider_id, surface_id, policy_hash, payload_json
            FROM policy_profiles WHERE policy_id=? AND version=?
            """,
            (profile.policy_id, profile.version),
        ).fetchone()
        if existing is not None:
            if (
                existing["provider_id"] == profile.provider_id
                and existing["surface_id"] == profile.surface_id
                and existing["policy_hash"] == profile.policy_hash
                and existing["payload_json"] == payload
            ):
                return
            raise TrustedStoreConflict(
                f"conflicting stored policy profile {profile.policy_id}@{profile.version}"
            )
        self._conn.execute(
            """
            INSERT INTO policy_profiles
                (policy_id, version, provider_id, surface_id, policy_hash, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                profile.policy_id,
                profile.version,
                profile.provider_id,
                profile.surface_id,
                profile.policy_hash,
                payload,
            ),
        )
        self._conn.commit()

    def get_policy_profile_payload(self, policy_id: str, version: str) -> dict:
        row = self._conn.execute(
            "SELECT payload_json FROM policy_profiles WHERE policy_id=? AND version=?",
            (policy_id, version),
        ).fetchone()
        if row is None:
            raise KeyError((policy_id, version))
        return json.loads(row["payload_json"])

    def save_usage_envelope(self, envelope: UsageEnvelope) -> None:
        self._conn.execute(
            """
            INSERT INTO usage_envelopes (envelope_id, asset_ref, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(envelope_id) DO UPDATE SET
                asset_ref=excluded.asset_ref,
                payload_json=excluded.payload_json
            """,
            (envelope.envelope_id, envelope.asset_ref, _dump(envelope)),
        )
        self._conn.commit()

    def get_usage_envelope(self, envelope_id: str) -> UsageEnvelope:
        row = self._conn.execute(
            "SELECT payload_json FROM usage_envelopes WHERE envelope_id=?", (envelope_id,)
        ).fetchone()
        if row is None:
            raise KeyError(envelope_id)
        data = json.loads(row["payload_json"])
        return UsageEnvelope(
            envelope_id=data["envelope_id"],
            asset_ref=data["asset_ref"],
            permissions=tuple(AcquisitionAction(v) for v in data["permissions"]),
            prohibitions=tuple(AcquisitionAction(v) for v in data["prohibitions"]),
            obligations=tuple(
                Obligation(
                    obligation_id=o["obligation_id"],
                    kind=o["kind"],
                    parameters=o["parameters"],
                    persists_downstream=o["persists_downstream"],
                    policy_refs=tuple(o["policy_refs"]),
                )
                for o in data["obligations"]
            ),
            limits=tuple(
                PolicyLimit(
                    limit_id=l["limit_id"],
                    kind=l["kind"],
                    value=l["value"],
                    unit=l["unit"],
                    window=l["window"],
                    policy_refs=tuple(l["policy_refs"]),
                )
                for l in data["limits"]
            ),
            source_policy_refs=tuple(data["source_policy_refs"]),
            inherited_from=tuple(data["inherited_from"]),
            created_at=data["created_at"],
            evaluator_version=data["evaluator_version"],
            metadata=data["metadata"],
        )

    def save_acquired_asset(self, asset: AcquiredAsset) -> None:
        self._conn.execute(
            """
            INSERT INTO acquired_assets
                (asset_id, observation_id, provider_id, surface_id, usage_envelope_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                observation_id=excluded.observation_id,
                provider_id=excluded.provider_id,
                surface_id=excluded.surface_id,
                usage_envelope_id=excluded.usage_envelope_id,
                payload_json=excluded.payload_json
            """,
            (
                asset.asset_id,
                asset.observation_id,
                asset.provider_id,
                asset.surface_id,
                asset.usage_envelope_id,
                _dump(asset),
            ),
        )
        self._conn.commit()

    def get_acquired_asset(self, asset_id: str) -> AcquiredAsset:
        row = self._conn.execute(
            "SELECT payload_json FROM acquired_assets WHERE asset_id=?", (asset_id,)
        ).fetchone()
        if row is None:
            raise KeyError(asset_id)
        data = json.loads(row["payload_json"])
        artifact = data["artifact_ref"]
        return AcquiredAsset(
            asset_id=data["asset_id"],
            observation_id=data["observation_id"],
            provider_id=data["provider_id"],
            surface_id=data["surface_id"],
            artifact_ref=ArtifactRef(
                ArtifactKind(artifact["kind"]),
                artifact["id"],
                version=artifact["version"],
                metadata=artifact["metadata"],
            ),
            raw_ref=data["raw_ref"],
            media_type=data["media_type"],
            retrieved_at=data["retrieved_at"],
            content_hash=data["content_hash"],
            usage_envelope_id=data["usage_envelope_id"],
            acquisition_event_id=data["acquisition_event_id"],
            metadata=data["metadata"],
        )

    def save_anchor(self, anchor: EvidenceAnchor) -> None:
        self._conn.execute(
            """
            INSERT INTO evidence_anchors (anchor_id, anchor_kind, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(anchor_id) DO UPDATE SET
                anchor_kind=excluded.anchor_kind,
                payload_json=excluded.payload_json
            """,
            (anchor.anchor_id, anchor.kind.value, _dump(anchor)),
        )
        self._conn.commit()

    def get_anchor(self, anchor_id: str) -> EvidenceAnchor:
        row = self._conn.execute(
            "SELECT payload_json FROM evidence_anchors WHERE anchor_id=?", (anchor_id,)
        ).fetchone()
        if row is None:
            raise KeyError(anchor_id)
        data = json.loads(row["payload_json"])
        return EvidenceAnchor(
            anchor_id=data["anchor_id"],
            kind=AnchorKind(data["kind"]),
            manifestation_id=data["manifestation_id"],
            locator=data["locator"],
            anchored_text=data["anchored_text"],
            anchored_hash=data["anchored_hash"],
            created_at=data["created_at"],
            metadata=data["metadata"],
        )

    def save_candidate_evidence(self, candidate: CandidateEvidence) -> None:
        self._conn.execute(
            """
            INSERT INTO candidate_evidence
                (candidate_evidence_id, acquired_asset_id, source_type, usage_envelope_id, payload_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(candidate_evidence_id) DO UPDATE SET
                acquired_asset_id=excluded.acquired_asset_id,
                source_type=excluded.source_type,
                usage_envelope_id=excluded.usage_envelope_id,
                payload_json=excluded.payload_json
            """,
            (
                candidate.candidate_evidence_id,
                candidate.acquired_asset_id,
                candidate.source_type,
                candidate.usage_envelope_id,
                _dump(candidate),
            ),
        )
        self._conn.commit()

    def get_candidate_evidence(self, candidate_id: str) -> CandidateEvidence:
        row = self._conn.execute(
            "SELECT payload_json FROM candidate_evidence WHERE candidate_evidence_id=?", (candidate_id,)
        ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        data = json.loads(row["payload_json"])
        return CandidateEvidence(
            candidate_evidence_id=data["candidate_evidence_id"],
            acquired_asset_id=data["acquired_asset_id"],
            field_name=data["field_name"],
            extracted_value=data["extracted_value"],
            source_identity_ref=data["source_identity_ref"],
            work_identity_ref=data["work_identity_ref"],
            version_identity_ref=data["version_identity_ref"],
            manifestation_identity_ref=data["manifestation_identity_ref"],
            anchor_refs=tuple(data["anchor_refs"]),
            extraction_method=data["extraction_method"],
            extractor_version=data["extractor_version"],
            model_ref=data["model_ref"],
            source_type=data["source_type"],
            usage_envelope_id=data["usage_envelope_id"],
            extractor_confidence=data["extractor_confidence"],
            semantic_support_verified=data["semantic_support_verified"],
            validation_notes=tuple(data["validation_notes"]),
            created_at=data["created_at"],
        )

    def append_ledger_event(
        self,
        *,
        event_id: str,
        event_type: str,
        subject_type: str,
        subject_id: str,
        actor_id: str,
        actor_version: str | None,
        input_refs: tuple[str, ...],
        output_refs: tuple[str, ...],
        payload: dict,
        created_at: str,
    ) -> EvidenceLedgerEvent:
        payload_json = _dump(
            {
                "actor_id": actor_id,
                "actor_version": actor_version,
                "input_refs": input_refs,
                "output_refs": output_refs,
                "payload": payload,
                "created_at": created_at,
            }
        )
        cur = self._conn.execute(
            """
            INSERT INTO evidence_ledger_events
                (event_id, event_type, subject_type, subject_id, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, event_type, subject_type, subject_id, payload_json),
        )
        self._conn.commit()
        sequence = int(cur.lastrowid)
        return EvidenceLedgerEvent(
            sequence=sequence,
            event_id=event_id,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            actor_id=actor_id,
            actor_version=actor_version,
            input_refs=input_refs,
            output_refs=output_refs,
            payload=payload,
            created_at=created_at,
        )

    def list_ledger_events(self) -> tuple[EvidenceLedgerEvent, ...]:
        rows = self._conn.execute(
            """
            SELECT sequence, event_id, event_type, subject_type, subject_id, payload_json
            FROM evidence_ledger_events ORDER BY sequence ASC
            """
        ).fetchall()
        result = []
        for row in rows:
            data = json.loads(row["payload_json"])
            result.append(
                EvidenceLedgerEvent(
                    sequence=row["sequence"],
                    event_id=row["event_id"],
                    event_type=row["event_type"],
                    subject_type=row["subject_type"],
                    subject_id=row["subject_id"],
                    actor_id=data["actor_id"],
                    actor_version=data["actor_version"],
                    input_refs=tuple(data["input_refs"]),
                    output_refs=tuple(data["output_refs"]),
                    payload=data["payload"],
                    created_at=data["created_at"],
                )
            )
        return tuple(result)

    def save_gap_projection(self, projection: GapProjection) -> None:
        self._conn.execute(
            """
            INSERT INTO gap_projections (gap_projection_id, claim_id, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(gap_projection_id) DO UPDATE SET
                claim_id=excluded.claim_id,
                payload_json=excluded.payload_json
            """,
            (projection.gap_projection_id, projection.claim_id, _dump(projection)),
        )
        self._conn.commit()

    def get_gap_projection(self, projection_id: str) -> GapProjection:
        row = self._conn.execute(
            "SELECT payload_json FROM gap_projections WHERE gap_projection_id=?", (projection_id,)
        ).fetchone()
        if row is None:
            raise KeyError(projection_id)
        data = json.loads(row["payload_json"])
        return GapProjection(
            gap_projection_id=data["gap_projection_id"],
            claim_id=data["claim_id"],
            evidence_refs=tuple(data["evidence_refs"]),
            gap_types=tuple(EvidenceGapType(v) for v in data["gap_types"]),
            mandatory=data["mandatory"],
            severity=data["severity"],
            reason_codes=tuple(data["reason_codes"]),
            created_at=data["created_at"],
        )
