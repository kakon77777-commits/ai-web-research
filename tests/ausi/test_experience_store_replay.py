import sqlite3
from pathlib import Path
import pytest
from ai_web_research.core.types import VersionRef
from ai_web_research.experience.dataset import SearchExperienceDataset
from ai_web_research.experience.models import ExperienceOutcome, SearchExperienceRecord
from ai_web_research.experience.prior import build_planner_prior
from ai_web_research.experience.store import ExperienceStoreConflict, SearchExperienceStore

class BaseStore:
    def __init__(self,path):
        self._conn=sqlite3.connect(path)
        self._conn.row_factory=sqlite3.Row
        self._conn.execute('CREATE TABLE receipt_marker(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self._conn.execute("INSERT INTO receipt_marker VALUES('r1','preserved')")
        self._conn.commit()
    def close(self): self._conn.close()

def rec(i='1',provider='provider.a',outcome=ExperienceOutcome.SUCCESS):
    return SearchExperienceRecord(
        experience_id=f'exp:{i}',source_receipt_id=f'receipt:{i}',source_action_receipt_id=f'ar:{i}',
        task_id='task:1',epoch_id='epoch:1',task_class='research',method_ref=VersionRef('method.lexical_search','1.0.0'),
        provider_ref=VersionRef(provider,'1.0.0'),surface_id='surface',binding_id='binding',outcome=outcome,
        result_count=1,artifact_count=1,candidate_gain=1,verified_evidence_gain=1,independent_root_gain=1,
        gaps_resolved=1,gaps_opened=0,normalized_cost=.2,latency_ms=100.0,policy_decision='allow',
        reason_codes=(),fact_refs=('fact:1',),observed_at='2026-09-03T14:00:00Z',metadata={},resolved_gap_types=('missing_identity',))

def test_store_is_additive_roundtrips_records_dataset_prior_and_preserves_base_tables(tmp_path):
    base=BaseStore(tmp_path/'x.db'); store=SearchExperienceStore(base)
    try:
        item=rec(); ds=SearchExperienceDataset('dataset:1',(item,),('receipt:1',)); prior=build_planner_prior(ds,'research')
        store.save_record(item); store.save_dataset(ds); store.save_prior(prior)
        assert store.get_record(item.experience_id)==item
        assert store.list_records(task_class='research')==(item,)
        assert store.get_dataset('dataset:1')==ds
        assert store.get_prior(prior.prior_id)==prior
        assert base._conn.execute("SELECT value FROM receipt_marker WHERE id='r1'").fetchone()['value']=='preserved'
    finally: base.close()

def test_immutable_records_are_idempotent_but_conflicting_payload_is_rejected(tmp_path):
    base=BaseStore(tmp_path/'x.db'); store=SearchExperienceStore(base)
    try:
        item=rec(); store.save_record(item); store.save_record(item)
        changed=SearchExperienceRecord(**{**item.__dict__,'latency_ms':999.0})
        with pytest.raises(ExperienceStoreConflict): store.save_record(changed)
    finally: base.close()

def test_persisted_payloads_do_not_contain_secret_or_cot_surfaces(tmp_path):
    base=BaseStore(tmp_path/'x.db'); store=SearchExperienceStore(base)
    try:
        item=rec(); ds=SearchExperienceDataset('dataset:1',(item,),('receipt:1',)); prior=build_planner_prior(ds,'research')
        store.save_record(item); store.save_dataset(ds); store.save_prior(prior)
        rows=[]
        for table in ('search_experience_records','experience_dataset_snapshots','planner_prior_snapshots'):
            rows.extend(r['payload_json'].lower() for r in base._conn.execute(f'SELECT payload_json FROM {table}'))
        joined=' '.join(rows)
        for token in ('chain_of_thought','private_reasoning','hidden_reasoning','credential_value','api_key','access_token'):
            assert token not in joined
    finally: base.close()
