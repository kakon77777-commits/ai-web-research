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

class ClaimEvidenceRelationType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    BACKGROUND = "background"


@dataclass(frozen=True)
class VerifiedEvidence:
    """Promoted evidence record.

    This means the declared promotion verification policy passed. It does
    not imply semantic support for any claim; claim linking is a separate gate.
    """

    evidence_id: str
    candidate_evidence_id: str
    acquired_asset_id: str
    source_identity_ref: str | None
    work_identity_ref: str | None
    version_identity_ref: str | None
    manifestation_identity_ref: str | None
    anchor_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    usage_envelope_id: str
    status: EvidenceStatus
    created_at: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required_text = {
            "evidence_id": self.evidence_id,
            "candidate_evidence_id": self.candidate_evidence_id,
            "acquired_asset_id": self.acquired_asset_id,
            "usage_envelope_id": self.usage_envelope_id,
            "created_at": self.created_at,
        }
        for name, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.verification_refs:
            raise ValueError("verification_refs must be non-empty")
        if self.status in {EvidenceStatus.DISCOVERED, EvidenceStatus.ACQUIRED}:
            raise ValueError("VerifiedEvidence status must be beyond discovery/acquisition")


@dataclass(frozen=True)
class EvidenceProvenance:
    provenance_id: str
    evidence_id: str
    source_identity_ref: str
    source_family_id: str | None
    independent_root_ref: str
    root_resolved: bool
    lineage_relation_refs: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("provenance_id", self.provenance_id),
            ("evidence_id", self.evidence_id),
            ("source_identity_ref", self.source_identity_ref),
            ("independent_root_ref", self.independent_root_ref),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class ClaimEvidenceRelation:
    relation_id: str
    claim_id: str
    evidence_id: str
    relation_type: ClaimEvidenceRelationType
    semantic_verification_ref: str
    provenance_ref: str
    confidence: float | None
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("relation_id", self.relation_id),
            ("claim_id", self.claim_id),
            ("evidence_id", self.evidence_id),
            ("semantic_verification_ref", self.semantic_verification_ref),
            ("provenance_ref", self.provenance_ref),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class ClaimEvidenceAssessment:
    claim_id: str
    status: EvidenceStatus
    supporting_evidence_refs: tuple[str, ...]
    contradicting_evidence_refs: tuple[str, ...]
    qualifying_evidence_refs: tuple[str, ...]
    background_evidence_refs: tuple[str, ...]
    independent_support_root_refs: tuple[str, ...]
    independent_contradiction_root_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, str) or not self.claim_id.strip():
            raise ValueError("claim_id must be non-empty")

    @property
    def independent_support_root_count(self) -> int:
        return len(set(self.independent_support_root_refs))

    @property
    def independent_contradiction_root_count(self) -> int:
        return len(set(self.independent_contradiction_root_refs))
