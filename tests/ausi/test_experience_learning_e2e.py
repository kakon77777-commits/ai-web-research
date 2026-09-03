import sqlite3
from ai_web_research.core.types import VersionRef
from ai_web_research.execution.models import ObservationStatus, PolicyDecision
from ai_web_research.experience.dataset import ExperienceDerivationContext
from ai_web_research.experience.models import ExperienceOutcome, ExperienceYieldFact
from ai_web_research.experience.receipt import SearchActionReceipt, SearchReceipt, SearchReceiptStatus
from ai_web_research.experience.runtime import ExperienceLearningRuntime
from ai_web_research.experience.store import SearchExperienceStore

class BaseStore:
    def __init__(self,path):
        self._conn=sqlite3.connect(path); self._conn.row_factory=sqlite3.Row
    def close(self): self._conn.close()

def action(aid, provider, *, status=ObservationStatus.SUCCEEDED, policy=PolicyDecision.ALLOW, results=2, usd=.1):
    return SearchActionReceipt(
        f'ar:{aid}','task:1','epoch:1',aid,VersionRef('method.lexical_search','1.0.0'),VersionRef(provider,'1.0.0'),
        f's:{provider}',f'b:{provider}',policy,('policy:1',),(),None if status is None else f'obs:{aid}',status,results,
        ('artifact:1',) if results else (),{} if usd is None else {'usd':usd},100.0 if status is not None else None,(),
        '2026-09-03T15:00:00Z',{})

def receipt():
    return SearchReceipt('receipt:1','task:1','epoch:1','registry:1','planner.autonomous.v1','0.4.0',(
        action('a','provider.a',results=4,usd=.2),
        action('b','provider.b',status=ObservationStatus.FAILED,results=None,usd=.1),
        action('c','provider.c',status=None,policy=PolicyDecision.DENY,results=None,usd=None),
    ),'SATURATION_REACHED',SearchReceiptStatus.PARTIAL,'2026-09-03T15:01:00Z',{})

def test_receipt_to_experience_metrics_prior_replay_and_authority_boundary(tmp_path):
    base=BaseStore(tmp_path/'experience.db'); store=SearchExperienceStore(base); runtime=ExperienceLearningRuntime(store)
    contexts={'task:1':ExperienceDerivationContext('research',(
        ExperienceYieldFact('ar:a',4,2,2,2,0,('ledger:a',),('missing_identity','unverified_semantic_support')),
        ExperienceYieldFact('ar:b',0,0,0,0,1,('ledger:b',),()),
    ))}
    try:
        first=runtime.learn((receipt(),),contexts)
        second=runtime.learn((receipt(),),contexts)
        assert first == second
        assert first.dataset.snapshot_id == second.dataset.snapshot_id
        assert len(first.dataset.records)==3
        outcomes={r.provider_ref.id:r.outcome for r in first.dataset.records}
        assert outcomes == {'provider.a':ExperienceOutcome.SUCCESS,'provider.b':ExperienceOutcome.FAILED,'provider.c':ExperienceOutcome.BLOCKED}
        prior=first.priors[0]
        assert prior.rank_providers('method.lexical_search',('provider.b','provider.a')) == ('provider.a','provider.b')
        # If eligibility/policy supplies only the historically worse provider, prior cannot reintroduce A.
        assert prior.rank_providers('method.lexical_search',('provider.b',)) == ('provider.b',)
        assert prior.rank_providers('method.lexical_search',()) == ()
        loaded=store.get_prior(prior.prior_id)
        assert loaded == prior
        assert store.get_dataset(first.dataset.snapshot_id) == first.dataset
        assert len(store.list_records(task_class='research'))==3
    finally:
        base.close()
