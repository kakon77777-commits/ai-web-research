from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import JsonValue, SearchState, SearchTask


@dataclass(frozen=True)
class PlanningGap:
    gap_ref: str
    gap_type: str
    priority: int


@dataclass(frozen=True)
class PlanningBudget:
    max_actions: int = 4
    max_parallel_branches: int = 2
    max_loop_iterations: int = 2
    max_provider_fallbacks: int = 1


@dataclass(frozen=True)
class PlanningPolicy:
    policy_id: str
    allow_experimental: bool = False
    enable_query_divergence: bool = True
    enable_provider_fallback: bool = True


@dataclass(frozen=True)
class ProposedMethodStep:
    step_id: str
    objective: str
    candidate_method_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchStrategyProposal:
    proposal_id: str
    task_id: str
    steps: tuple[ProposedMethodStep, ...]
    replan_condition_ref: str | None
    max_replans: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PlanningDecisionSummary:
    proposal_id: str
    method_corpus_snapshot_id: str
    provider_state_snapshot_id: str
    selected_method_ids: tuple[str, ...]
    skipped_method_ids: tuple[str, ...]
    skip_reasons: tuple[tuple[str, tuple[str, ...]], ...]
    routing_summaries: tuple[dict[str, JsonValue], ...]
    gap_refs: tuple[str, ...]
    budget: PlanningBudget


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _intersect_limit(task_budget: dict[str, JsonValue], state_budget: dict[str, JsonValue], key: str, default: int) -> int:
    values = [
        value
        for value in (
            _positive_int(task_budget.get(key)),
            _positive_int(state_budget.get(key)),
        )
        if value is not None
    ]
    return min(values) if values else default


def planning_budget_from(task: SearchTask, state: SearchState) -> PlanningBudget:
    return PlanningBudget(
        max_actions=_intersect_limit(task.budget, state.budget_state, "max_actions", 4),
        max_parallel_branches=_intersect_limit(task.budget, state.budget_state, "max_parallel_branches", 2),
        max_loop_iterations=_intersect_limit(task.budget, state.budget_state, "max_loop_iterations", 2),
        max_provider_fallbacks=_intersect_limit(task.budget, state.budget_state, "max_provider_fallbacks", 1),
    )


def planning_gaps_from_state(state: SearchState) -> tuple[PlanningGap, ...]:
    raw_details = state.metadata.get("gap_details", {})
    details = raw_details if isinstance(raw_details, dict) else {}
    gaps: list[PlanningGap] = []
    for gap_ref in state.open_gap_refs:
        raw = details.get(gap_ref, {})
        item = raw if isinstance(raw, dict) else {}
        gap_type_raw = item.get("type", "unknown")
        gap_type = gap_type_raw if isinstance(gap_type_raw, str) and gap_type_raw else "unknown"
        priority_raw = item.get("priority", 0)
        priority = priority_raw if isinstance(priority_raw, int) and not isinstance(priority_raw, bool) else 0
        gaps.append(PlanningGap(gap_ref=gap_ref, gap_type=gap_type, priority=priority))
    return tuple(gaps)
