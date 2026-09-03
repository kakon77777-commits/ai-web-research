from dataclasses import FrozenInstanceError, fields
import pytest
from ai_web_research.core.types import VersionRef
from ai_web_research.experience.models import (
    ExperienceOutcome, ExperienceYieldFact, SearchExperienceRecord,
)

def record(**overrides):
    values=dict(
        experience_id='exp:1', source_receipt_id='receipt:1', source_action_receipt_id='ar:1',
        task_id='task:1', epoch_id='epoch:1', task_class='research',
        method_ref=VersionRef('method.lexical_search','1.0.0'),
        provider_ref=VersionRef('provider.a','1.0.0'), surface_id='surface.a', binding_id='binding.a',
        outcome=ExperienceOutcome.SUCCESS, result_count=3, artifact_count=2,
        candidate_gain=2, verified_evidence_gain=1, independent_root_gain=1,
        gaps_resolved=1, gaps_opened=0, normalized_cost=0.2, latency_ms=100.0,
        policy_decision='allow', reason_codes=('EXPLICIT_PERMISSION',),
        fact_refs=('ledger:1',), observed_at='2026-09-03T14:00:00Z', metadata={},
    )
    values.update(overrides)
    return SearchExperienceRecord(**values)

def test_outcomes_distinguish_execution_from_policy_control():
    assert ExperienceOutcome.SUCCESS.executed is True
    assert ExperienceOutcome.FAILED.executed is True
    assert ExperienceOutcome.BLOCKED.executed is False
    assert ExperienceOutcome.REVIEW.executed is False
    assert ExperienceOutcome.BLOCKED.provider_failure is False
    assert ExperienceOutcome.FAILED.provider_failure is True

def test_yield_fact_preserves_unknown_vs_zero_and_validates_nonnegative():
    fact=ExperienceYieldFact(action_receipt_id='ar:a1', candidate_gain=None, verified_evidence_gain=0,
        independent_root_gain=None, gaps_resolved=2, gaps_opened=0, fact_refs=('event:1',))
    assert fact.candidate_gain is None
    assert fact.verified_evidence_gain == 0
    with pytest.raises(ValueError):
        ExperienceYieldFact('ar:a1',-1,None,None,None,None,())

def test_record_is_immutable_and_disallows_negative_observable_metrics():
    item=record()
    with pytest.raises(FrozenInstanceError):
        item.task_class='other'
    with pytest.raises(ValueError):
        record(latency_ms=-1)
    with pytest.raises(ValueError):
        record(verified_evidence_gain=-1)

def test_experience_schema_has_no_authorization_secret_or_reasoning_fields():
    names={f.name.lower() for f in fields(SearchExperienceRecord)}
    forbidden={'authorization','authorized','credential','credential_value','api_key','access_token',
               'chain_of_thought','reasoning','private_reasoning','hidden_reasoning'}
    assert not names.intersection(forbidden)
