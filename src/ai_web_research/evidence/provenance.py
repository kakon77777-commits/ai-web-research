from __future__ import annotations

from ai_web_research.source_graph.models import (
    SourceFamilyResolution,
    SourceRelation,
    SourceRelationType,
)

from .models import EvidenceProvenance, VerifiedEvidence


_LINEAGE_TYPES = {
    SourceRelationType.SYNDICATED_FROM,
    SourceRelationType.MIRRORS,
    SourceRelationType.DERIVED_FROM,
    SourceRelationType.TRANSLATED_FROM,
    SourceRelationType.SAME_ORIGIN_FAMILY,
}


def resolve_evidence_provenance(
    evidence: VerifiedEvidence,
    family_resolution: SourceFamilyResolution,
    relations: tuple[SourceRelation, ...] = (),
) -> EvidenceProvenance:
    source_id = evidence.source_identity_ref
    if not source_id:
        raise ValueError("VerifiedEvidence requires source identity for provenance resolution")

    family_id = family_resolution.source_to_family.get(source_id)
    if family_id is None:
        return EvidenceProvenance(
            provenance_id=f"{evidence.evidence_id}:provenance",
            evidence_id=evidence.evidence_id,
            source_identity_ref=source_id,
            source_family_id=None,
            independent_root_ref=f"unresolved:{source_id}",
            root_resolved=False,
            lineage_relation_refs=(),
            created_at=evidence.created_at,
        )

    family = family_resolution.families[family_id]
    members = set(family.member_source_ids)
    lineage_refs = tuple(
        sorted(
            relation.relation_id
            for relation in relations
            if relation.relation_type in _LINEAGE_TYPES
            and relation.from_source_id in members
            and relation.to_source_id in members
        )
    )
    root_ref = (
        family.root_source_id
        if family.root_resolved
        else f"unresolved-family:{family.family_id}"
    )
    return EvidenceProvenance(
        provenance_id=f"{evidence.evidence_id}:provenance",
        evidence_id=evidence.evidence_id,
        source_identity_ref=source_id,
        source_family_id=family.family_id,
        independent_root_ref=root_ref,
        root_resolved=family.root_resolved,
        lineage_relation_refs=lineage_refs,
        created_at=evidence.created_at,
    )
