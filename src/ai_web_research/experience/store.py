from __future__ import annotations
import json
from ai_web_research.core.types import VersionRef
from .dataset import SearchExperienceDataset
from .models import ExperienceOutcome, SearchExperienceRecord
from .prior import MethodPriorEntry, PlannerPriorSnapshot, ProviderPriorEntry

class ExperienceStoreConflict(ValueError):
    pass

_SCHEMA='''
CREATE TABLE IF NOT EXISTS search_experience_records (
    experience_id TEXT PRIMARY KEY,
    task_class TEXT NOT NULL,
    method_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_experience_task_method
ON search_experience_records(task_class, method_id, experience_id);
CREATE INDEX IF NOT EXISTS idx_search_experience_provider
ON search_experience_records(task_class, provider_id, experience_id);
CREATE TABLE IF NOT EXISTS experience_dataset_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planner_prior_snapshots (
    prior_id TEXT PRIMARY KEY,
    task_class TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
'''

def _canonical(value):
    if value is None or isinstance(value,(str,int,float,bool)): return value
    if hasattr(value,'value'): return value.value
    if isinstance(value,dict): return {str(k):_canonical(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set,frozenset)): return [_canonical(v) for v in value]
    if hasattr(value,'__dataclass_fields__'):
        return {name:_canonical(getattr(value,name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)

def _dump(value): return json.dumps(_canonical(value),ensure_ascii=False,sort_keys=True,separators=(',',':'))

class SearchExperienceStore:
    def __init__(self, receipt_store) -> None:
        self.receipt_store=receipt_store
        self._conn=receipt_store._conn
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _save(self,table,id_column,id_value,payload,insert_sql,params):
        row=self._conn.execute(f'SELECT payload_json FROM {table} WHERE {id_column}=?',(id_value,)).fetchone()
        if row is not None:
            if row['payload_json']==payload: return
            raise ExperienceStoreConflict(f'conflicting immutable record {table}:{id_value}')
        self._conn.execute(insert_sql,params); self._conn.commit()

    def save_record(self,record:SearchExperienceRecord)->None:
        payload=_dump(record)
        self._save('search_experience_records','experience_id',record.experience_id,payload,
            'INSERT INTO search_experience_records(experience_id,task_class,method_id,provider_id,payload_json) VALUES(?,?,?,?,?)',
            (record.experience_id,record.task_class,record.method_ref.id,record.provider_ref.id,payload))

    @staticmethod
    def _decode_record(data:dict)->SearchExperienceRecord:
        return SearchExperienceRecord(
            experience_id=data['experience_id'],source_receipt_id=data['source_receipt_id'],
            source_action_receipt_id=data['source_action_receipt_id'],task_id=data['task_id'],epoch_id=data['epoch_id'],
            task_class=data['task_class'],method_ref=VersionRef(data['method_ref']['id'],data['method_ref']['version']),
            provider_ref=VersionRef(data['provider_ref']['id'],data['provider_ref']['version']),surface_id=data['surface_id'],
            binding_id=data['binding_id'],outcome=ExperienceOutcome(data['outcome']),result_count=data['result_count'],
            artifact_count=data['artifact_count'],candidate_gain=data['candidate_gain'],verified_evidence_gain=data['verified_evidence_gain'],
            independent_root_gain=data['independent_root_gain'],gaps_resolved=data['gaps_resolved'],gaps_opened=data['gaps_opened'],
            normalized_cost=data['normalized_cost'],latency_ms=data['latency_ms'],policy_decision=data['policy_decision'],
            reason_codes=tuple(data['reason_codes']),fact_refs=tuple(data['fact_refs']),observed_at=data['observed_at'],
            metadata=data['metadata'],resolved_gap_types=tuple(data.get('resolved_gap_types',())),
        )

    def get_record(self,experience_id:str)->SearchExperienceRecord:
        row=self._conn.execute('SELECT payload_json FROM search_experience_records WHERE experience_id=?',(experience_id,)).fetchone()
        if row is None: raise KeyError(experience_id)
        return self._decode_record(json.loads(row['payload_json']))

    def list_records(self,*,task_class:str|None=None,method_id:str|None=None,provider_id:str|None=None)->tuple[SearchExperienceRecord,...]:
        clauses=[]; params=[]
        for column,value in (('task_class',task_class),('method_id',method_id),('provider_id',provider_id)):
            if value is not None: clauses.append(f'{column}=?'); params.append(value)
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        rows=self._conn.execute(f'SELECT experience_id FROM search_experience_records{where} ORDER BY experience_id',tuple(params)).fetchall()
        return tuple(self.get_record(row['experience_id']) for row in rows)

    def save_dataset(self,dataset:SearchExperienceDataset)->None:
        payload=_dump(dataset)
        self._save('experience_dataset_snapshots','snapshot_id',dataset.snapshot_id,payload,
                   'INSERT INTO experience_dataset_snapshots(snapshot_id,payload_json) VALUES(?,?)',(dataset.snapshot_id,payload))

    def get_dataset(self,snapshot_id:str)->SearchExperienceDataset:
        row=self._conn.execute('SELECT payload_json FROM experience_dataset_snapshots WHERE snapshot_id=?',(snapshot_id,)).fetchone()
        if row is None: raise KeyError(snapshot_id)
        data=json.loads(row['payload_json'])
        return SearchExperienceDataset(data['snapshot_id'],tuple(self._decode_record(r) for r in data['records']),tuple(data['source_receipt_ids']),data.get('derivation_version','0.7.0'))

    def save_prior(self,prior:PlannerPriorSnapshot)->None:
        payload=_dump(prior)
        self._save('planner_prior_snapshots','prior_id',prior.prior_id,payload,
                   'INSERT INTO planner_prior_snapshots(prior_id,task_class,payload_json) VALUES(?,?,?)',(prior.prior_id,prior.task_class,payload))

    def get_prior(self,prior_id:str)->PlannerPriorSnapshot:
        row=self._conn.execute('SELECT payload_json FROM planner_prior_snapshots WHERE prior_id=?',(prior_id,)).fetchone()
        if row is None: raise KeyError(prior_id)
        data=json.loads(row['payload_json'])
        methods=tuple(MethodPriorEntry(**item) for item in data['method_entries'])
        providers=tuple(ProviderPriorEntry(**item) for item in data['provider_entries'])
        return PlannerPriorSnapshot(data['prior_id'],data['dataset_snapshot_id'],data['task_class'],methods,providers,data.get('prior_version','0.7.0'))
