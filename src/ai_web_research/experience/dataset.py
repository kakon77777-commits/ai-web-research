from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from ai_web_research.execution.models import ObservationStatus, PolicyDecision
from .models import ExperienceOutcome, ExperienceYieldFact, SearchExperienceRecord
from .receipt import SearchReceipt

@dataclass(frozen=True)
class ExperienceDerivationContext:
    task_class: str
    yield_facts: tuple[ExperienceYieldFact,...]=()
    def __post_init__(self)->None:
        if not self.task_class.strip():
            raise ValueError('task_class must be non-empty')
        ids=[fact.action_receipt_id for fact in self.yield_facts]
        if len(ids)!=len(set(ids)):
            raise ValueError('duplicate yield fact action_receipt_id')


def _outcome(action)->ExperienceOutcome:
    if action.policy_decision is PolicyDecision.REVIEW:
        return ExperienceOutcome.REVIEW
    if action.policy_decision in {PolicyDecision.DENY, PolicyDecision.UNKNOWN}:
        return ExperienceOutcome.BLOCKED
    if action.observation_status is ObservationStatus.FAILED or 'PROVIDER_EXECUTION_ERROR' in action.reason_codes:
        return ExperienceOutcome.FAILED
    if action.observation_status is ObservationStatus.PARTIAL:
        return ExperienceOutcome.PARTIAL
    if action.observation_status is ObservationStatus.SUCCEEDED:
        if action.result_count == 0:
            return ExperienceOutcome.EMPTY
        return ExperienceOutcome.SUCCESS
    return ExperienceOutcome.FAILED


def _normalized_cost(cost:dict)->float|None:
    for key in ('usd','cost_usd','estimated_usd','total_usd'):
        value=cost.get(key)
        if isinstance(value,(int,float)) and not isinstance(value,bool) and value >= 0:
            return float(value)
    return None


def derive_search_experience(receipt:SearchReceipt, context:ExperienceDerivationContext)->tuple[SearchExperienceRecord,...]:
    facts={fact.action_receipt_id:fact for fact in context.yield_facts}
    result=[]
    for action in receipt.actions:
        fact=facts.get(action.action_receipt_id)
        material=f'{receipt.receipt_id}|{action.action_receipt_id}|{context.task_class}'
        eid='experience:'+sha256(material.encode('utf-8')).hexdigest()[:24]
        result.append(SearchExperienceRecord(
            experience_id=eid,
            source_receipt_id=receipt.receipt_id,
            source_action_receipt_id=action.action_receipt_id,
            task_id=action.task_id,
            epoch_id=action.epoch_id,
            task_class=context.task_class,
            method_ref=action.method_ref,
            provider_ref=action.provider_ref,
            surface_id=action.surface_id,
            binding_id=action.binding_id,
            outcome=_outcome(action),
            result_count=action.result_count,
            artifact_count=len(action.artifact_refs),
            candidate_gain=(fact.candidate_gain if fact else None),
            verified_evidence_gain=(fact.verified_evidence_gain if fact else None),
            independent_root_gain=(fact.independent_root_gain if fact else None),
            gaps_resolved=(fact.gaps_resolved if fact else None),
            gaps_opened=(fact.gaps_opened if fact else None),
            normalized_cost=_normalized_cost(action.cost),
            latency_ms=action.latency_ms,
            policy_decision=action.policy_decision.value,
            reason_codes=tuple(action.reason_codes),
            fact_refs=tuple(sorted(fact.fact_refs)) if fact else (),
            observed_at=action.occurred_at,
            metadata={
                'receipt_status': receipt.status.value,
                'stop_reason': receipt.stop_reason,
            },
            resolved_gap_types=tuple(sorted(fact.resolved_gap_types)) if fact else (),
        ))
    return tuple(result)


def _canonical_record(record:SearchExperienceRecord)->dict:
    def norm(v):
        if hasattr(v,'value'): return v.value
        if hasattr(v,'__dataclass_fields__'):
            return {name:norm(getattr(v,name)) for name in v.__dataclass_fields__}
        if isinstance(v,dict): return {str(k):norm(val) for k,val in sorted(v.items())}
        if isinstance(v,(tuple,list)): return [norm(x) for x in v]
        return v
    return norm(record)

@dataclass(frozen=True)
class SearchExperienceDataset:
    snapshot_id: str
    records: tuple[SearchExperienceRecord,...]
    source_receipt_ids: tuple[str,...]
    derivation_version: str = '0.7.0'

    @classmethod
    def build(cls, receipts:tuple[SearchReceipt,...], contexts:dict[str,ExperienceDerivationContext]):
        receipt_ids=[receipt.receipt_id for receipt in receipts]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError('duplicate receipt_id in experience dataset input')
        action_receipt_ids=[action.action_receipt_id for receipt in receipts for action in receipt.actions]
        if len(action_receipt_ids) != len(set(action_receipt_ids)):
            raise ValueError('duplicate action_receipt_id in experience dataset input')
        all_records=[]
        source_ids=[]
        for receipt in sorted(receipts,key=lambda r:r.receipt_id):
            context=contexts.get(receipt.task_id)
            if context is None:
                raise KeyError(f'missing experience context for {receipt.task_id}')
            source_ids.append(receipt.receipt_id)
            all_records.extend(derive_search_experience(receipt,context))
        records=tuple(sorted(all_records,key=lambda r:r.experience_id))
        payload=json.dumps({'derivation_version':'0.7.0','records':[_canonical_record(r) for r in records]},ensure_ascii=False,sort_keys=True,separators=(',',':'))
        snapshot='experience-dataset:'+sha256(payload.encode('utf-8')).hexdigest()
        return cls(snapshot,records,tuple(sorted(source_ids)))
