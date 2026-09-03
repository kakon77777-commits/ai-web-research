from ai_web_research.core.types import VersionRef
from ai_web_research.execution.models import ObservationStatus, PolicyDecision
from ai_web_research.experience.dataset import (
    ExperienceDerivationContext, SearchExperienceDataset, derive_search_experience,
)
from ai_web_research.experience.models import ExperienceOutcome, ExperienceYieldFact
from ai_web_research.experience.receipt import SearchActionReceipt, SearchReceipt, SearchReceiptStatus

def action(aid, *, provider='provider.a', policy=PolicyDecision.ALLOW, status=ObservationStatus.SUCCEEDED, results=2, cost=None):
    return SearchActionReceipt(
        action_receipt_id=f'ar:{aid}', task_id='task:1', epoch_id='epoch:1', action_id=aid,
        method_ref=VersionRef('method.lexical_search','1.0.0'), provider_ref=VersionRef(provider,'1.0.0'),
        surface_id=f'surface:{provider}', binding_id=f'binding:{provider}', policy_decision=policy,
        policy_refs=('policy:1',), reason_codes=(), observation_id=(None if status is None else f'obs:{aid}'),
        observation_status=status, result_count=results, artifact_refs=('artifact:1',) if results else (),
        cost=cost or {}, latency_ms=50.0 if status is not None else None, gap_refs=(),
        occurred_at='2026-09-03T14:00:00Z', metadata={'unsafe_arbitrary':'must-not-copy'},
    )

def receipt(actions):
    return SearchReceipt('receipt:1','task:1','epoch:1','registry:1','planner:1','0.4.0',tuple(actions),
                         'SATURATION_REACHED',SearchReceiptStatus.PARTIAL,'2026-09-03T14:01:00Z',{})

def test_derivation_maps_observable_outcomes_and_keeps_unknown_yields_unknown():
    r=receipt((
        action('ok'),
        action('empty',results=0),
        action('partial',status=ObservationStatus.PARTIAL),
        action('failed',status=ObservationStatus.FAILED,results=None),
        action('deny',policy=PolicyDecision.DENY,status=None,results=None),
        action('review',policy=PolicyDecision.REVIEW,status=None,results=None),
    ))
    records=derive_search_experience(r, ExperienceDerivationContext('research'))
    assert [x.outcome for x in records] == [
        ExperienceOutcome.SUCCESS,ExperienceOutcome.EMPTY,ExperienceOutcome.PARTIAL,
        ExperienceOutcome.FAILED,ExperienceOutcome.BLOCKED,ExperienceOutcome.REVIEW,
    ]
    assert records[0].candidate_gain is None
    assert records[0].verified_evidence_gain is None
    assert 'unsafe_arbitrary' not in records[0].metadata

def test_yield_facts_and_normalized_usd_cost_are_attached_by_action_id():
    r=receipt((action('ok',cost={'usd':0.25,'requests':1}),))
    ctx=ExperienceDerivationContext('research', yield_facts=(
        ExperienceYieldFact('ar:ok',2,1,1,3,1,('ledger:evidence:1','gap:event:1')),
    ))
    item=derive_search_experience(r,ctx)[0]
    assert item.candidate_gain == 2
    assert item.verified_evidence_gain == 1
    assert item.independent_root_gain == 1
    assert item.gaps_resolved == 3
    assert item.gaps_opened == 1
    assert item.normalized_cost == 0.25
    assert item.fact_refs == ('gap:event:1','ledger:evidence:1')

def test_cost_without_explicit_currency_key_stays_unknown_not_sum_of_counters():
    item=derive_search_experience(receipt((action('ok',cost={'requests':4,'tokens':1000}),)),
                                  ExperienceDerivationContext('research'))[0]
    assert item.normalized_cost is None

def test_dataset_snapshot_is_deterministic_across_receipt_input_order():
    r1=receipt((action('a'),))
    r2=SearchReceipt('receipt:2','task:2','epoch:2','registry:1','planner:1','0.4.0',
        (SearchActionReceipt(**{**action('b').__dict__,'task_id':'task:2','epoch_id':'epoch:2','action_receipt_id':'ar:b2'}),),
        'DONE',SearchReceiptStatus.COMPLETE,'2026-09-03T14:02:00Z',{})
    contexts={'task:1':ExperienceDerivationContext('research'),'task:2':ExperienceDerivationContext('verify')}
    one=SearchExperienceDataset.build((r1,r2),contexts)
    two=SearchExperienceDataset.build((r2,r1),contexts)
    assert one.snapshot_id == two.snapshot_id
    assert one.records == two.records
    assert len(one.records)==2

def test_duplicate_receipt_ids_are_rejected_to_prevent_double_counting():
    import pytest
    r=receipt((action('a'),))
    with pytest.raises(ValueError,match='duplicate receipt_id'):
        SearchExperienceDataset.build((r,r),{'task:1':ExperienceDerivationContext('research')})

def test_yield_fact_is_scoped_to_action_receipt_identity_not_action_id():
    base=action('same')
    r=receipt((base,))
    ctx=ExperienceDerivationContext('research',yield_facts=(
        ExperienceYieldFact(base.action_receipt_id,1,1,1,1,0,('fact:exact',),('missing_identity',)),
    ))
    item=derive_search_experience(r,ctx)[0]
    assert item.verified_evidence_gain==1
    assert item.fact_refs==('fact:exact',)
    assert item.resolved_gap_types==('missing_identity',)

def test_duplicate_action_receipt_identity_across_receipts_is_rejected():
    import pytest
    a=action('same')
    r1=receipt((a,))
    r2=SearchReceipt('receipt:2','task:1','epoch:2','registry:1','planner:1','0.4.0',
        (SearchActionReceipt(**{**a.__dict__,'epoch_id':'epoch:2'}),),
        'DONE',SearchReceiptStatus.COMPLETE,'2026-09-03T14:02:00Z',{})
    with pytest.raises(ValueError,match='duplicate action_receipt_id'):
        SearchExperienceDataset.build((r1,r2),{'task:1':ExperienceDerivationContext('research')})
