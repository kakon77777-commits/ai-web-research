from dataclasses import fields
from ai_web_research.core.types import VersionRef
from ai_web_research.experience.metrics import aggregate_experience
from ai_web_research.experience.models import ExperienceOutcome, SearchExperienceRecord
from ai_web_research.experience.prior import PlannerPriorSnapshot, build_planner_prior
from ai_web_research.experience.dataset import SearchExperienceDataset

def rec(i, provider, outcome, *, evidence=None, gaps=None, cost=None, latency=100.0, method='method.lexical_search'):
    return SearchExperienceRecord(
        experience_id=f'exp:{i}',source_receipt_id=f'r:{i}',source_action_receipt_id=f'ar:{i}',
        task_id=f't:{i}',epoch_id=f'e:{i}',task_class='research',
        method_ref=VersionRef(method,'1.0.0'),provider_ref=VersionRef(provider,'1.0.0'),
        surface_id=f's:{provider}',binding_id=f'b:{provider}',outcome=outcome,result_count=2 if outcome is ExperienceOutcome.SUCCESS else None,
        artifact_count=1 if outcome is ExperienceOutcome.SUCCESS else 0,candidate_gain=None,
        verified_evidence_gain=evidence,independent_root_gain=None,gaps_resolved=gaps,gaps_opened=None,
        normalized_cost=cost,latency_ms=latency,policy_decision='allow' if outcome.executed else 'deny',
        reason_codes=(),fact_refs=(),observed_at='2026-09-03T14:00:00Z',metadata={})

def dataset(records):
    return SearchExperienceDataset('dataset:1',tuple(records),tuple(sorted({r.source_receipt_id for r in records})))

def test_aggregates_separate_provider_failure_from_policy_block_and_preserve_unknown_yields():
    ds=dataset((
        rec(1,'provider.a',ExperienceOutcome.SUCCESS,evidence=2,gaps=1,cost=.2),
        rec(2,'provider.a',ExperienceOutcome.SUCCESS,evidence=None,gaps=None,cost=.3),
        rec(3,'provider.b',ExperienceOutcome.FAILED,evidence=0,gaps=0,cost=.1),
        rec(4,'provider.c',ExperienceOutcome.BLOCKED),
    ))
    by_provider=aggregate_experience(ds,task_class='research',group_by='provider')
    a=next(x for x in by_provider if x.provider_id=='provider.a')
    b=next(x for x in by_provider if x.provider_id=='provider.b')
    c=next(x for x in by_provider if x.provider_id=='provider.c')
    assert a.executed_count==2 and a.success_count==2 and a.success_rate==1.0
    assert a.verified_evidence_known_count==1 and a.verified_evidence_gain_total==2
    assert a.average_verified_evidence_gain==2.0
    assert b.provider_failure_count==1 and b.provider_failure_rate==1.0
    assert c.policy_blocked_count==1 and c.provider_failure_count==0 and c.executed_count==0

def test_cost_and_latency_efficiency_use_observed_values_only():
    ds=dataset((rec(1,'provider.a',ExperienceOutcome.SUCCESS,evidence=2,gaps=1,cost=.5,latency=1000),))
    a=aggregate_experience(ds,task_class='research',group_by='provider')[0]
    assert a.average_cost==.5
    assert a.average_latency_ms==1000.0
    assert a.evidence_per_cost==4.0
    assert a.evidence_per_latency_second==2.0

def test_prior_ranks_successful_evidence_yielding_provider_first_but_only_reorders_supplied_candidates():
    ds=dataset((
        rec(1,'provider.a',ExperienceOutcome.SUCCESS,evidence=2,gaps=2,cost=.2,latency=100),
        rec(2,'provider.a',ExperienceOutcome.SUCCESS,evidence=1,gaps=1,cost=.2,latency=110),
        rec(3,'provider.b',ExperienceOutcome.FAILED,evidence=0,gaps=0,cost=.1,latency=500),
        rec(4,'provider.c',ExperienceOutcome.BLOCKED),
    ))
    prior=build_planner_prior(ds,'research')
    assert prior.rank_providers('method.lexical_search',('provider.b','provider.a')) == ('provider.a','provider.b')
    # A is historically preferred, but an eligibility layer that supplies only B stays authoritative.
    assert prior.rank_providers('method.lexical_search',('provider.b',)) == ('provider.b',)
    # Unknown candidate is preserved rather than removed or replaced.
    assert set(prior.rank_providers('method.lexical_search',('provider.unknown','provider.a'))) == {'provider.unknown','provider.a'}

def test_prior_ranks_methods_by_task_class_and_has_no_authorization_surface():
    ds=dataset((
        rec(1,'provider.a',ExperienceOutcome.SUCCESS,evidence=2,gaps=2,method='method.lexical_search'),
        rec(2,'provider.a',ExperienceOutcome.FAILED,evidence=0,gaps=0,method='method.exact_search'),
    ))
    prior=build_planner_prior(ds,'research')
    assert prior.rank_methods(('method.exact_search','method.lexical_search')) == ('method.lexical_search','method.exact_search')
    names={f.name.lower() for f in fields(PlannerPriorSnapshot)}
    forbidden={'authorization','authorized','policy_decision','credential','credential_profile_id','api_key','chain_of_thought','reasoning'}
    assert not names.intersection(forbidden)

def test_gap_resolution_metric_is_method_and_gap_type_specific():
    from ai_web_research.experience.metrics import aggregate_gap_resolution
    r1=rec(10,'provider.a',ExperienceOutcome.SUCCESS,evidence=1,gaps=2)
    r2=rec(11,'provider.a',ExperienceOutcome.SUCCESS,evidence=1,gaps=1)
    r1=SearchExperienceRecord(**{**r1.__dict__,'resolved_gap_types':('missing_identity','missing_identity')})
    r2=SearchExperienceRecord(**{**r2.__dict__,'resolved_gap_types':('unverified_semantic_support',)})
    metrics=aggregate_gap_resolution(dataset((r1,r2)),task_class='research')
    by_type={m.gap_type:m for m in metrics}
    assert by_type['missing_identity'].resolution_count == 2
    assert by_type['unverified_semantic_support'].resolution_count == 1
    assert all(m.method_id=='method.lexical_search' for m in metrics)

def test_dataset_and_prior_have_explicit_algorithm_versions():
    ds=dataset((rec(20,'provider.a',ExperienceOutcome.SUCCESS,evidence=1,gaps=1),))
    prior=build_planner_prior(ds,'research')
    assert ds.derivation_version == '0.7.0'
    assert prior.prior_version == '0.7.0'

def test_candidate_and_independent_root_yield_are_aggregated_separately():
    base=rec(30,'provider.a',ExperienceOutcome.SUCCESS,evidence=2,gaps=1)
    one=SearchExperienceRecord(**{**base.__dict__,'candidate_gain':5,'independent_root_gain':2})
    two=SearchExperienceRecord(**{**rec(31,'provider.a',ExperienceOutcome.SUCCESS,evidence=1,gaps=1).__dict__,
                                  'candidate_gain':None,'independent_root_gain':1})
    agg=aggregate_experience(dataset((one,two)),task_class='research',group_by='provider')[0]
    assert agg.candidate_gain_total == 5
    assert agg.candidate_gain_known_count == 1
    assert agg.average_candidate_gain == 5.0
    assert agg.independent_root_gain_total == 3
    assert agg.independent_root_gain_known_count == 2
    assert agg.average_independent_root_gain == 1.5
