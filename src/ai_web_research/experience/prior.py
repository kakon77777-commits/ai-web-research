from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from .dataset import SearchExperienceDataset
from .metrics import ExperienceAggregate, aggregate_experience

@dataclass(frozen=True)
class MethodPriorEntry:
    method_id: str
    sample_size: int
    executed_count: int
    success_rate: float
    partial_rate: float
    provider_failure_rate: float
    average_verified_evidence_gain: float | None
    average_gap_resolution: float | None
    average_cost: float | None
    average_latency_ms: float | None

@dataclass(frozen=True)
class ProviderPriorEntry:
    method_id: str
    provider_id: str
    sample_size: int
    executed_count: int
    success_rate: float
    partial_rate: float
    provider_failure_rate: float
    average_verified_evidence_gain: float | None
    average_gap_resolution: float | None
    average_cost: float | None
    average_latency_ms: float | None

@dataclass(frozen=True)
class PlannerPriorSnapshot:
    prior_id: str
    dataset_snapshot_id: str
    task_class: str
    method_entries: tuple[MethodPriorEntry,...]
    provider_entries: tuple[ProviderPriorEntry,...]
    prior_version: str = '0.7.0'

    def rank_methods(self, candidate_method_ids: tuple[str,...]) -> tuple[str,...]:
        rank={entry.method_id:i for i,entry in enumerate(self.method_entries)}
        indexed=list(enumerate(candidate_method_ids))
        indexed.sort(key=lambda pair:(rank.get(pair[1],10**9), pair[0]))
        return tuple(item for _,item in indexed)

    def rank_providers(self, method_id: str, candidate_provider_ids: tuple[str,...]) -> tuple[str,...]:
        ordered=[entry.provider_id for entry in self.provider_entries if entry.method_id==method_id]
        rank={pid:i for i,pid in enumerate(ordered)}
        indexed=list(enumerate(candidate_provider_ids))
        indexed.sort(key=lambda pair:(rank.get(pair[1],10**9), pair[0]))
        return tuple(item for _,item in indexed)


def _metric_sort_key(a: ExperienceAggregate):
    # Preference-only ranking. Blocked-only/review-only history never becomes an executed success.
    return (
        1 if a.executed_count > 0 else 0,
        a.success_rate,
        a.partial_rate,
        a.average_verified_evidence_gain if a.average_verified_evidence_gain is not None else -1.0,
        a.average_gap_resolution if a.average_gap_resolution is not None else -1.0,
        -a.provider_failure_rate,
        -(a.average_cost if a.average_cost is not None else 10**12),
        -(a.average_latency_ms if a.average_latency_ms is not None else 10**12),
        a.executed_count,
        a.record_count,
    )


def build_planner_prior(dataset: SearchExperienceDataset, task_class: str) -> PlannerPriorSnapshot:
    methods=sorted(aggregate_experience(dataset,task_class=task_class,group_by='method'),
                   key=lambda a:(_metric_sort_key(a),a.method_id or ''),reverse=True)
    providers=sorted(aggregate_experience(dataset,task_class=task_class,group_by='method_provider'),
                     key=lambda a:(_metric_sort_key(a),a.method_id or '',a.provider_id or ''),reverse=True)
    method_entries=tuple(MethodPriorEntry(
        method_id=a.method_id or '',sample_size=a.record_count,executed_count=a.executed_count,
        success_rate=a.success_rate,partial_rate=a.partial_rate,provider_failure_rate=a.provider_failure_rate,
        average_verified_evidence_gain=a.average_verified_evidence_gain,average_gap_resolution=a.average_gap_resolution,
        average_cost=a.average_cost,average_latency_ms=a.average_latency_ms) for a in methods)
    provider_entries=tuple(ProviderPriorEntry(
        method_id=a.method_id or '',provider_id=a.provider_id or '',sample_size=a.record_count,executed_count=a.executed_count,
        success_rate=a.success_rate,partial_rate=a.partial_rate,provider_failure_rate=a.provider_failure_rate,
        average_verified_evidence_gain=a.average_verified_evidence_gain,average_gap_resolution=a.average_gap_resolution,
        average_cost=a.average_cost,average_latency_ms=a.average_latency_ms) for a in providers)
    material=f'0.7.0|{dataset.snapshot_id}|{task_class}|'+repr(method_entries)+'|'+repr(provider_entries)
    prior_id='planner-prior:'+sha256(material.encode('utf-8')).hexdigest()
    return PlannerPriorSnapshot(prior_id,dataset.snapshot_id,task_class,method_entries,provider_entries)
