from __future__ import annotations
from dataclasses import dataclass
from .dataset import ExperienceDerivationContext, SearchExperienceDataset
from .metrics import ExperienceAggregate, GapResolutionMetric, aggregate_experience, aggregate_gap_resolution
from .prior import PlannerPriorSnapshot, build_planner_prior
from .receipt import SearchReceipt

@dataclass(frozen=True)
class ExperienceLearningResult:
    dataset: SearchExperienceDataset
    priors: tuple[PlannerPriorSnapshot,...]
    method_metrics: tuple[ExperienceAggregate,...]
    provider_metrics: tuple[ExperienceAggregate,...]
    gap_metrics: tuple[GapResolutionMetric,...]

class ExperienceLearningRuntime:
    runtime_id='experience.learning.v0.7'
    runtime_version='0.7.0'
    def __init__(self, store) -> None:
        self.store=store

    def learn(self, receipts: tuple[SearchReceipt,...], contexts: dict[str,ExperienceDerivationContext]) -> ExperienceLearningResult:
        dataset=SearchExperienceDataset.build(receipts,contexts)
        for record in dataset.records:
            self.store.save_record(record)
        self.store.save_dataset(dataset)
        task_classes=tuple(sorted({contexts[receipt.task_id].task_class for receipt in receipts}))
        priors=[]; method_metrics=[]; provider_metrics=[]; gap_metrics=[]
        for task_class in task_classes:
            prior=build_planner_prior(dataset,task_class)
            self.store.save_prior(prior)
            priors.append(prior)
            method_metrics.extend(aggregate_experience(dataset,task_class=task_class,group_by='method'))
            provider_metrics.extend(aggregate_experience(dataset,task_class=task_class,group_by='method_provider'))
            gap_metrics.extend(aggregate_gap_resolution(dataset,task_class=task_class))
        return ExperienceLearningResult(dataset,tuple(priors),tuple(method_metrics),tuple(provider_metrics),tuple(gap_metrics))
