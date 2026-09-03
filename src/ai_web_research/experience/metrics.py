from __future__ import annotations
from dataclasses import dataclass
from .dataset import SearchExperienceDataset
from .models import ExperienceOutcome

@dataclass(frozen=True)
class ExperienceAggregate:
    task_class: str
    method_id: str | None
    provider_id: str | None
    record_count: int
    executed_count: int
    success_count: int
    empty_count: int
    partial_count: int
    provider_failure_count: int
    policy_blocked_count: int
    review_count: int
    candidate_gain_total: int
    candidate_gain_known_count: int
    verified_evidence_gain_total: int
    verified_evidence_known_count: int
    independent_root_gain_total: int
    independent_root_gain_known_count: int
    gaps_resolved_total: int
    gaps_resolved_known_count: int
    normalized_cost_total: float
    cost_known_count: int
    latency_total_ms: float
    latency_known_count: int

    @property
    def success_rate(self) -> float:
        return self.success_count / self.executed_count if self.executed_count else 0.0

    @property
    def partial_rate(self) -> float:
        return self.partial_count / self.executed_count if self.executed_count else 0.0

    @property
    def provider_failure_rate(self) -> float:
        return self.provider_failure_count / self.executed_count if self.executed_count else 0.0

    @property
    def average_candidate_gain(self) -> float | None:
        return self.candidate_gain_total / self.candidate_gain_known_count if self.candidate_gain_known_count else None

    @property
    def average_verified_evidence_gain(self) -> float | None:
        return self.verified_evidence_gain_total / self.verified_evidence_known_count if self.verified_evidence_known_count else None

    @property
    def average_independent_root_gain(self) -> float | None:
        return self.independent_root_gain_total / self.independent_root_gain_known_count if self.independent_root_gain_known_count else None

    @property
    def average_gap_resolution(self) -> float | None:
        return self.gaps_resolved_total / self.gaps_resolved_known_count if self.gaps_resolved_known_count else None

    @property
    def average_cost(self) -> float | None:
        return self.normalized_cost_total / self.cost_known_count if self.cost_known_count else None

    @property
    def average_latency_ms(self) -> float | None:
        return self.latency_total_ms / self.latency_known_count if self.latency_known_count else None

    @property
    def evidence_per_cost(self) -> float | None:
        if not self.verified_evidence_known_count or self.normalized_cost_total <= 0:
            return None
        return self.verified_evidence_gain_total / self.normalized_cost_total

    @property
    def evidence_per_latency_second(self) -> float | None:
        if not self.verified_evidence_known_count or self.latency_total_ms <= 0:
            return None
        return self.verified_evidence_gain_total / (self.latency_total_ms / 1000.0)


def aggregate_experience(dataset: SearchExperienceDataset, *, task_class: str, group_by: str) -> tuple[ExperienceAggregate,...]:
    if group_by not in {'method','provider','method_provider'}:
        raise ValueError('group_by must be method, provider, or method_provider')
    groups: dict[tuple[str|None,str|None],list] = {}
    for record in dataset.records:
        if record.task_class != task_class:
            continue
        key=(
            record.method_ref.id if group_by in {'method','method_provider'} else None,
            record.provider_ref.id if group_by in {'provider','method_provider'} else None,
        )
        groups.setdefault(key,[]).append(record)

    out=[]
    for (method_id,provider_id), records in sorted(groups.items(), key=lambda item: (item[0][0] or '', item[0][1] or '')):
        executed=[r for r in records if r.outcome.executed]
        candidates=[r.candidate_gain for r in records if r.candidate_gain is not None]
        evidence=[r.verified_evidence_gain for r in records if r.verified_evidence_gain is not None]
        roots=[r.independent_root_gain for r in records if r.independent_root_gain is not None]
        gaps=[r.gaps_resolved for r in records if r.gaps_resolved is not None]
        costs=[r.normalized_cost for r in records if r.normalized_cost is not None]
        latencies=[r.latency_ms for r in records if r.latency_ms is not None]
        out.append(ExperienceAggregate(
            task_class=task_class,
            method_id=method_id,
            provider_id=provider_id,
            record_count=len(records),
            executed_count=len(executed),
            success_count=sum(r.outcome is ExperienceOutcome.SUCCESS for r in records),
            empty_count=sum(r.outcome is ExperienceOutcome.EMPTY for r in records),
            partial_count=sum(r.outcome is ExperienceOutcome.PARTIAL for r in records),
            provider_failure_count=sum(r.outcome.provider_failure for r in records),
            policy_blocked_count=sum(r.outcome is ExperienceOutcome.BLOCKED for r in records),
            review_count=sum(r.outcome is ExperienceOutcome.REVIEW for r in records),
            candidate_gain_total=sum(candidates),
            candidate_gain_known_count=len(candidates),
            verified_evidence_gain_total=sum(evidence),
            verified_evidence_known_count=len(evidence),
            independent_root_gain_total=sum(roots),
            independent_root_gain_known_count=len(roots),
            gaps_resolved_total=sum(gaps),
            gaps_resolved_known_count=len(gaps),
            normalized_cost_total=float(sum(costs)),
            cost_known_count=len(costs),
            latency_total_ms=float(sum(latencies)),
            latency_known_count=len(latencies),
        ))
    return tuple(out)

@dataclass(frozen=True)
class GapResolutionMetric:
    task_class: str
    method_id: str
    gap_type: str
    resolution_count: int
    supporting_record_count: int


def aggregate_gap_resolution(dataset: SearchExperienceDataset, *, task_class: str) -> tuple[GapResolutionMetric,...]:
    counts: dict[tuple[str,str], int] = {}
    records: dict[tuple[str,str], set[str]] = {}
    for record in dataset.records:
        if record.task_class != task_class:
            continue
        for gap_type in record.resolved_gap_types:
            key=(record.method_ref.id,gap_type)
            counts[key]=counts.get(key,0)+1
            records.setdefault(key,set()).add(record.experience_id)
    return tuple(
        GapResolutionMetric(task_class,method_id,gap_type,counts[(method_id,gap_type)],len(records[(method_id,gap_type)]))
        for method_id,gap_type in sorted(counts)
    )
