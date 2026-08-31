from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from ai_web_research.core.types import ArtifactRef, JsonValue
from ai_web_research.policy.models import UsageEnvelope

if TYPE_CHECKING:
    from .anchors import EvidenceAnchor
    from .verifier import VerificationResult


@dataclass(frozen=True)
class AcquiredAsset:
    asset_id: str
    observation_id: str
    provider_id: str
    surface_id: str
    artifact_ref: ArtifactRef
    raw_ref: str | None
    media_type: str | None
    retrieved_at: str
    content_hash: str | None
    usage_envelope_id: str
    acquisition_event_id: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class MaterializedAsset:
    asset: AcquiredAsset
    usage_envelope: UsageEnvelope


class EvidenceStatus(StrEnum):
    DISCOVERED = "discovered"
    ACQUIRED = "acquired"
    IDENTIFIED = "identified"
    ANCHORED = "anchored"
    FIXITY_VERIFIED = "fixity_verified"
    CONTENT_VERIFIED = "content_verified"
    CLAIM_LINKED = "claim_linked"
    CORROBORATED = "corroborated"
    CONTESTED = "contested"
    QUALIFIED = "qualified"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"
    POLICY_RESTRICTED = "policy_restricted"


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_evidence_id: str
    acquired_asset_id: str
    field_name: str
    extracted_value: JsonValue
    source_identity_ref: str | None
    work_identity_ref: str | None
    version_identity_ref: str | None
    manifestation_identity_ref: str | None
    anchor_refs: tuple[str, ...]
    extraction_method: str
    extractor_version: str | None
    model_ref: str | None
    source_type: str
    usage_envelope_id: str
    extractor_confidence: float | None
    semantic_support_verified: bool
    validation_notes: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class CandidateEvidenceMaterialization:
    candidates: tuple[CandidateEvidence, ...]
    anchors: tuple["EvidenceAnchor", ...]
    verifications: tuple["VerificationResult", ...]
    gap_hints: tuple[str, ...]
