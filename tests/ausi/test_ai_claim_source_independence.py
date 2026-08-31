from ai_web_research.domains.ai_industry.canonicalize import promote_claim
from ai_web_research.domains.ai_industry.models import ClaimDraft
from ai_web_research.domains.ai_industry.source_independence import attach_independent_root_count
from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.knowledge.models import ClaimOrigin, ClaimState
from ai_web_research.source_graph.family import resolve_source_families
from ai_web_research.source_graph.models import RelationInferenceType, SourceNode, SourceRelation, SourceRelationType


def evidence(eid, source_id):
    return CandidateEvidence(
        candidate_evidence_id=eid,
        acquired_asset_id=f'asset:{eid}',
        field_name='claim',
        extracted_value='Model X released',
        source_identity_ref=source_id,
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=(f'anchor:{eid}',),
        extraction_method='fixture',
        extractor_version='v1',
        model_ref=None,
        source_type='fixture',
        usage_envelope_id='usage:1',
        extractor_confidence=1.0,
        semantic_support_verified=False,
        validation_notes=(),
        created_at='2026-08-31T15:00:00Z',
    )


def node(sid):
    return SourceNode(sid, f'https://{sid}.example/', None, None, '2026-08-31T15:00:00Z', None, None, {})


def draft():
    return ClaimDraft(
        claim_id='claim:release',
        statement='Model X released.',
        subject_id='model:x',
        predicate='released',
        object_value=True,
        state=ClaimState.CONFIRMED,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence=(evidence('ev:o','official'), evidence('ev:r','repo'), evidence('ev:a','media_a'), evidence('ev:b','media_b')),
        independent_root_count=0,
        known_at='2026-08-31T15:00:00Z',
        valid_time=None,
        metadata={},
    )


def resolution():
    nodes=(node('official'),node('repo'),node('media_a'),node('media_b'))
    relations=(
        SourceRelation('r1','media_a','official',SourceRelationType.DERIVED_FROM,1.0,RelationInferenceType.EXPLICIT,('attribution',)),
        SourceRelation('r2','media_b','media_a',SourceRelationType.SYNDICATED_FROM,1.0,RelationInferenceType.EXPLICIT,('syndication',)),
    )
    return resolve_source_families(nodes,relations)


def test_attaches_runtime_computed_independent_root_count_without_mutation():
    original=draft()
    updated=attach_independent_root_count(original, ('official','repo','media_a','media_b'), resolution())
    assert original.independent_root_count == 0
    assert updated.independent_root_count == 2
    claim=promote_claim(updated)
    assert claim.independent_root_count == 2
    assert claim.evidence_ids == ('ev:o','ev:r','ev:a','ev:b')


def test_unresolved_source_ids_count_independently():
    original=draft()
    updated=attach_independent_root_count(original, ('official','unknown-1','unknown-2'), resolution())
    assert updated.independent_root_count == 3


def test_empty_evidence_source_ids_yield_zero_roots():
    updated=attach_independent_root_count(draft(), (), resolution())
    assert updated.independent_root_count == 0
