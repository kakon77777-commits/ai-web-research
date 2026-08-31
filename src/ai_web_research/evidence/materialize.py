from __future__ import annotations

from hashlib import sha256

from ai_web_research.core.types import ArtifactKind
from ai_web_research.execution.models import AuthorizedAction, ObservationStatus, ProviderObservation
from ai_web_research.policy.models import UsageEnvelope

from .anchors import AnchorKind, EvidenceAnchor
from .models import AcquiredAsset, CandidateEvidence, CandidateEvidenceMaterialization, MaterializedAsset
from .verifier import VerificationDecision, VerificationDimension, VerificationResult


def materialize_acquired_assets(
    authorized: AuthorizedAction,
    observation: ProviderObservation,
) -> tuple[MaterializedAsset, ...]:
    if observation.status is ObservationStatus.FAILED:
        return ()
    if not authorized.authorization.is_executable:
        return ()
    seed = authorized.usage_seed
    if seed is None:
        return ()

    items: list[MaterializedAsset] = []
    for index, artifact in enumerate(observation.artifacts, start=1):
        asset_id = f"{observation.observation_id}:asset:{index}"
        envelope_id = f"{asset_id}:usage"
        envelope = UsageEnvelope(
            envelope_id=envelope_id,
            asset_ref=asset_id,
            permissions=seed.permissions,
            prohibitions=seed.prohibitions,
            obligations=seed.obligations,
            limits=seed.limits,
            source_policy_refs=seed.policy_refs,
            inherited_from=(),
            created_at=observation.occurred_at,
            evaluator_version="ausi-policy/0.1.0",
            metadata={},
        )
        media_type = artifact.metadata.get("media_type")
        content_hash = artifact.metadata.get("content_hash")
        asset = AcquiredAsset(
            asset_id=asset_id,
            observation_id=observation.observation_id,
            provider_id=observation.provider_id,
            surface_id=observation.surface_id,
            artifact_ref=artifact,
            raw_ref=observation.raw_ref,
            media_type=str(media_type) if media_type is not None else None,
            retrieved_at=observation.occurred_at,
            content_hash=str(content_hash) if content_hash is not None else None,
            usage_envelope_id=envelope_id,
            acquisition_event_id=f"{authorized.action.action_id}:acquired:{index}",
            metadata={
                "action_id": authorized.action.action_id,
                "policy_refs": list(authorized.authorization.policy_refs),
            },
        )
        items.append(MaterializedAsset(asset=asset, usage_envelope=envelope))
    return tuple(items)


def materialize_candidate_evidence(
    materialized: MaterializedAsset,
) -> CandidateEvidenceMaterialization:
    artifact = materialized.asset.artifact_ref
    if artifact.kind is not ArtifactKind.EVIDENCE_CANDIDATE:
        return CandidateEvidenceMaterialization((), (), (), ())

    source_type = str(artifact.metadata.get("source_type", "unknown"))
    if source_type == "llm_recall":
        return CandidateEvidenceMaterialization((), (), (), ())

    fields = artifact.metadata.get("fields")
    if not isinstance(fields, dict):
        return CandidateEvidenceMaterialization((), (), (), ("malformed_candidate_fields",))

    candidates: list[CandidateEvidence] = []
    anchors: list[EvidenceAnchor] = []
    verifications: list[VerificationResult] = []
    gap_hints: set[str] = set()
    created_at = materialized.asset.retrieved_at

    for field_name, field_value in fields.items():
        if not isinstance(field_value, dict):
            field_value = {}
        candidate_id = f"{materialized.asset.asset_id}:candidate:{field_name}"
        quote = field_value.get("source_quote")
        quote_verified = bool(field_value.get("quote_verified"))
        confidence = field_value.get("confidence")
        anchor_refs: tuple[str, ...] = ()

        if quote:
            quote_text = str(quote)
            anchor_id = f"{candidate_id}:anchor:1"
            anchored_hash = sha256(quote_text.encode("utf-8")).hexdigest()
            anchor = EvidenceAnchor(
                anchor_id=anchor_id,
                kind=AnchorKind.TEXT_SPAN,
                manifestation_id=None,
                locator={"source_quote": quote_text},
                anchored_text=quote_text,
                anchored_hash=anchored_hash,
                created_at=created_at,
                metadata={"legacy_quote_verification": quote_verified},
            )
            anchors.append(anchor)
            anchor_refs = (anchor_id,)

        decision = (
            VerificationDecision.PASS
            if quote and quote_verified
            else VerificationDecision.FAIL
        )
        reason = (
            ("LEGACY_QUOTE_VERIFIED",)
            if decision is VerificationDecision.PASS
            else ("ANCHOR_NOT_VERIFIED",)
        )
        verifications.append(
            VerificationResult(
                verification_id=f"{candidate_id}:verification:anchor",
                evidence_ref=candidate_id,
                claim_ref=None,
                dimension=VerificationDimension.ANCHOR,
                decision=decision,
                reason_codes=reason,
                verifier_id="legacy.quote_verifier",
                verifier_version=str(artifact.metadata.get("extractor_version") or "unknown"),
                input_refs=(materialized.asset.asset_id,),
                output_refs=anchor_refs,
                confidence=None,
                created_at=created_at,
            )
        )
        if decision is VerificationDecision.FAIL:
            gap_hints.add("unverified_anchor")

        raw_conf = confidence
        candidates.append(
            CandidateEvidence(
                candidate_evidence_id=candidate_id,
                acquired_asset_id=materialized.asset.asset_id,
                field_name=str(field_name),
                extracted_value=field_value.get("value"),
                source_identity_ref=None,
                work_identity_ref=None,
                version_identity_ref=None,
                manifestation_identity_ref=None,
                anchor_refs=anchor_refs,
                extraction_method="method.extract_candidate_evidence",
                extractor_version=(
                    str(artifact.metadata.get("extractor_version"))
                    if artifact.metadata.get("extractor_version") is not None
                    else None
                ),
                model_ref=(
                    str(artifact.metadata.get("model"))
                    if artifact.metadata.get("model") is not None
                    else None
                ),
                source_type=source_type,
                usage_envelope_id=materialized.asset.usage_envelope_id,
                extractor_confidence=(
                    float(raw_conf)
                    if isinstance(raw_conf, (int, float)) and not isinstance(raw_conf, bool)
                    else None
                ),
                semantic_support_verified=False,
                validation_notes=tuple(
                    str(item)
                    for item in artifact.metadata.get("validation_errors", [])
                    if item is not None
                ),
                created_at=created_at,
            )
        )

    return CandidateEvidenceMaterialization(
        candidates=tuple(candidates),
        anchors=tuple(anchors),
        verifications=tuple(verifications),
        gap_hints=tuple(sorted(gap_hints)),
    )
