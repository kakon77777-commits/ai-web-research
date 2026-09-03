from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from ai_web_research.core.types import JsonValue, VersionRef

class ExperienceOutcome(StrEnum):
    SUCCESS='success'
    EMPTY='empty'
    PARTIAL='partial'
    FAILED='failed'
    BLOCKED='blocked'
    REVIEW='review'

    @property
    def executed(self) -> bool:
        return self in {self.SUCCESS,self.EMPTY,self.PARTIAL,self.FAILED}

    @property
    def provider_failure(self) -> bool:
        return self is self.FAILED

@dataclass(frozen=True)
class ExperienceYieldFact:
    action_receipt_id: str
    candidate_gain: int|None
    verified_evidence_gain: int|None
    independent_root_gain: int|None
    gaps_resolved: int|None
    gaps_opened: int|None
    fact_refs: tuple[str,...]=()
    resolved_gap_types: tuple[str,...]=()
    def __post_init__(self)->None:
        if not self.action_receipt_id.strip():
            raise ValueError('action_receipt_id must be non-empty')
        for name in ('candidate_gain','verified_evidence_gain','independent_root_gain','gaps_resolved','gaps_opened'):
            value=getattr(self,name)
            if value is not None and value < 0:
                raise ValueError(f'{name} must be >= 0 when known')
        if any(not isinstance(item,str) or not item.strip() for item in self.resolved_gap_types):
            raise ValueError('resolved_gap_types must contain non-empty strings')

@dataclass(frozen=True)
class SearchExperienceRecord:
    experience_id: str
    source_receipt_id: str
    source_action_receipt_id: str
    task_id: str
    epoch_id: str
    task_class: str
    method_ref: VersionRef
    provider_ref: VersionRef
    surface_id: str
    binding_id: str
    outcome: ExperienceOutcome
    result_count: int|None
    artifact_count: int
    candidate_gain: int|None
    verified_evidence_gain: int|None
    independent_root_gain: int|None
    gaps_resolved: int|None
    gaps_opened: int|None
    normalized_cost: float|None
    latency_ms: float|None
    policy_decision: str
    reason_codes: tuple[str,...]
    fact_refs: tuple[str,...]
    observed_at: str
    metadata: dict[str,JsonValue]=field(default_factory=dict)
    resolved_gap_types: tuple[str,...]=()
    def __post_init__(self)->None:
        for name in ('experience_id','source_receipt_id','source_action_receipt_id','task_id','epoch_id','task_class','surface_id','binding_id','policy_decision','observed_at'):
            value=getattr(self,name)
            if not isinstance(value,str) or not value.strip():
                raise ValueError(f'{name} must be non-empty')
        for name in ('result_count','candidate_gain','verified_evidence_gain','independent_root_gain','gaps_resolved','gaps_opened'):
            value=getattr(self,name)
            if value is not None and value < 0:
                raise ValueError(f'{name} must be >= 0 when known')
        if self.artifact_count < 0:
            raise ValueError('artifact_count must be >= 0')
        if self.normalized_cost is not None and self.normalized_cost < 0:
            raise ValueError('normalized_cost must be >= 0')
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError('latency_ms must be >= 0')
        if any(not isinstance(item,str) or not item.strip() for item in self.resolved_gap_types):
            raise ValueError('resolved_gap_types must contain non-empty strings')
