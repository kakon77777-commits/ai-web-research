import pytest

from ai_web_research.evidence.claim_links import (
    ClaimLinkRejected,
    assess_claim_evidence,
    link_evidence_to_claim,
)
from ai_web_research.evidence.models import (
    ClaimEvidenceRelationType,
    EvidenceStatus,
    VerifiedEvidence,
)
from ai_web_research.evidence.provenance import resolve_evidence_provenance
from ai_web_research.evidence.verifier import (
    VerificationDecision,
    VerificationDimension,
    VerificationResult,
)
from ai_web_research.source_graph.family import resolve_source_families
from ai_web_research.source_graph.models import (
    RelationInferenceType,
    SourceNode,
    SourceRelation,
    SourceRelationType,
)


NOW = "2026-09-03T09:20:00+00:00"


def evidence(eid: str, source_id: str):
    return VerifiedEvidence(
        evidence_id=eid,
        candidate_evidence_id=f"{eid}:candidate",
        acquired_asset_id=f"{eid}:asset",
        source_identity_ref=source_id,
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=(f"{eid}:anchor",),
        verification_refs=(f"{eid}:anchor-v", f"{eid}:source-v"),
        usage_envelope_id=f"{eid}:usage",
        status=EvidenceStatus.ANCHORED,
        created_at=NOW,
        metadata={},
    )


def source(source_id: str, published: str):
    return SourceNode(
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        canonical_url=None,
        published_at=published,
        observed_at=NOW,
        owner_hint=None,
        content_hash=f"hash:{source_id}",
        metadata={},
    )


def relation(rid, from_id, to_id, relation_type):
    return SourceRelation(
        relation_id=rid,
        from_source_id=from_id,
        to_source_id=to_id,
        relation_type=relation_type,
        confidence=1.0,
        inference_type=RelationInferenceType.EXPLICIT,
        signals=("test",),
    )


def semantic(evidence_id: str, claim_id: str, *, decision=VerificationDecision.PASS):
    return VerificationResult(
        verification_id=f"semantic:{evidence_id}:{claim_id}:{decision.value}",
        evidence_ref=evidence_id,
        claim_ref=claim_id,
        dimension=VerificationDimension.SEMANTIC_SUPPORT,
        decision=decision,
        reason_codes=("SEMANTIC_RELATION_CHECKED",),
        verifier_id="semantic.verifier",
        verifier_version="1.0",
        input_refs=(evidence_id, claim_id),
        output_refs=(),
        confidence=0.9 if decision is VerificationDecision.PASS else None,
        created_at=NOW,
    )


def test_unknown_source_family_is_explicitly_unresolved_and_not_fake_independence():
    resolution = resolve_source_families((source("source:a", NOW),), ())
    item = evidence("evidence:x", "source:x")
    provenance = resolve_evidence_provenance(item, resolution)
    assert provenance.source_family_id is None
    assert provenance.independent_root_ref == "unresolved:source:x"
    assert provenance.root_resolved is False
    assert provenance.lineage_relation_refs == ()


def test_cites_does_not_collapse_source_family_or_independent_roots():
    nodes = (
        source("source:a", "2026-01-01"),
        source("source:b", "2026-01-02"),
    )
    cites = relation("rel:cites", "source:b", "source:a", SourceRelationType.CITES)
    resolution = resolve_source_families(nodes, (cites,))
    pa = resolve_evidence_provenance(evidence("evidence:a", "source:a"), resolution, (cites,))
    pb = resolve_evidence_provenance(evidence("evidence:b", "source:b"), resolution, (cites,))
    assert pa.source_family_id != pb.source_family_id
    assert pa.independent_root_ref != pb.independent_root_ref
    assert "rel:cites" not in pa.lineage_relation_refs
    assert "rel:cites" not in pb.lineage_relation_refs


def test_anchor_verification_cannot_create_claim_support_relation():
    item = evidence("evidence:a", "source:a")
    resolution = resolve_source_families((source("source:a", NOW),), ())
    provenance = resolve_evidence_provenance(item, resolution)
    anchor = VerificationResult(
        verification_id="anchor-only",
        evidence_ref=item.evidence_id,
        claim_ref="claim:1",
        dimension=VerificationDimension.ANCHOR,
        decision=VerificationDecision.PASS,
        reason_codes=("ANCHOR_VERIFIED",),
        verifier_id="anchor.verifier",
        verifier_version="1",
        input_refs=(),
        output_refs=(),
        confidence=1.0,
        created_at=NOW,
    )
    with pytest.raises(ClaimLinkRejected):
        link_evidence_to_claim(
            item,
            "claim:1",
            ClaimEvidenceRelationType.SUPPORTS,
            anchor,
            provenance,
            created_at=NOW,
        )


def test_same_family_support_is_one_independent_root_then_second_family_corroborates():
    nodes = (
        source("source:a", "2026-01-01"),
        source("source:a-mirror", "2026-01-02"),
        source("source:b", "2026-01-03"),
    )
    mirrored = relation(
        "rel:mirror",
        "source:a-mirror",
        "source:a",
        SourceRelationType.MIRRORS,
    )
    resolution = resolve_source_families(nodes, (mirrored,))

    ea = evidence("evidence:a", "source:a")
    em = evidence("evidence:mirror", "source:a-mirror")
    eb = evidence("evidence:b", "source:b")
    pa = resolve_evidence_provenance(ea, resolution, (mirrored,))
    pm = resolve_evidence_provenance(em, resolution, (mirrored,))
    pb = resolve_evidence_provenance(eb, resolution, (mirrored,))

    ra = link_evidence_to_claim(
        ea, "claim:1", ClaimEvidenceRelationType.SUPPORTS,
        semantic(ea.evidence_id, "claim:1"), pa, created_at=NOW,
    )
    rm = link_evidence_to_claim(
        em, "claim:1", ClaimEvidenceRelationType.SUPPORTS,
        semantic(em.evidence_id, "claim:1"), pm, created_at=NOW,
    )

    one_root = assess_claim_evidence(
        "claim:1", (ra, rm), (pa, pm),
        minimum_independent_support_roots=2,
    )
    assert one_root.status is EvidenceStatus.CLAIM_LINKED
    assert one_root.independent_support_root_count == 1
    assert len(one_root.supporting_evidence_refs) == 2

    rb = link_evidence_to_claim(
        eb, "claim:1", ClaimEvidenceRelationType.SUPPORTS,
        semantic(eb.evidence_id, "claim:1"), pb, created_at=NOW,
    )
    two_roots = assess_claim_evidence(
        "claim:1", (ra, rm, rb), (pa, pm, pb),
        minimum_independent_support_roots=2,
    )
    assert two_roots.status is EvidenceStatus.CORROBORATED
    assert two_roots.independent_support_root_count == 2


def test_independent_semantic_contradiction_produces_contested_assessment():
    nodes = (
        source("source:a", "2026-01-01"),
        source("source:c", "2026-01-02"),
    )
    resolution = resolve_source_families(nodes, ())
    ea = evidence("evidence:a", "source:a")
    ec = evidence("evidence:c", "source:c")
    pa = resolve_evidence_provenance(ea, resolution)
    pc = resolve_evidence_provenance(ec, resolution)

    support = link_evidence_to_claim(
        ea, "claim:1", ClaimEvidenceRelationType.SUPPORTS,
        semantic(ea.evidence_id, "claim:1"), pa, created_at=NOW,
    )
    contradiction = link_evidence_to_claim(
        ec, "claim:1", ClaimEvidenceRelationType.CONTRADICTS,
        semantic(ec.evidence_id, "claim:1"), pc, created_at=NOW,
    )
    assessment = assess_claim_evidence(
        "claim:1",
        (support, contradiction),
        (pa, pc),
        minimum_independent_support_roots=2,
    )
    assert assessment.status is EvidenceStatus.CONTESTED
    assert assessment.independent_contradiction_root_count == 1
    assert assessment.contradicting_evidence_refs == ("evidence:c",)


def test_semantic_verification_must_match_claim_and_evidence():
    item = evidence("evidence:a", "source:a")
    resolution = resolve_source_families((source("source:a", NOW),), ())
    provenance = resolve_evidence_provenance(item, resolution)

    with pytest.raises(ClaimLinkRejected):
        link_evidence_to_claim(
            item,
            "claim:1",
            ClaimEvidenceRelationType.SUPPORTS,
            semantic("evidence:other", "claim:1"),
            provenance,
            created_at=NOW,
        )
    with pytest.raises(ClaimLinkRejected):
        link_evidence_to_claim(
            item,
            "claim:1",
            ClaimEvidenceRelationType.SUPPORTS,
            semantic(item.evidence_id, "claim:other"),
            provenance,
            created_at=NOW,
        )
