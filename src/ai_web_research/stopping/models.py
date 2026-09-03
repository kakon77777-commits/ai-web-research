from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CoverageAxis(StrEnum):
    METHOD = "method"
    PROVIDER = "provider"
    SOURCE = "source"
    EVIDENCE = "evidence"
    JURISDICTION = "jurisdiction"
    LANGUAGE = "language"
    TEMPORAL = "temporal"
    DOMAIN = "domain"


@dataclass(frozen=True)
class CoverageMeasure:
    axis: CoverageAxis
    achieved: float
    target: float
    required: bool = True

    def __post_init__(self) -> None:
        if self.achieved < 0:
            raise ValueError("coverage achieved must be >= 0")
        if self.target < 0:
            raise ValueError("coverage target must be >= 0")
        if self.required and self.target <= 0:
            raise ValueError("required coverage target must be > 0")

    @property
    def met(self) -> bool:
        return self.achieved >= self.target


@dataclass(frozen=True)
class CoverageState:
    measures: tuple[CoverageMeasure, ...]
    open_material_gap_refs: tuple[str, ...]
    material_gap_assessment_complete: bool = False

    @property
    def confirmed_no_material_gaps(self) -> bool:
        return self.material_gap_assessment_complete and not self.open_material_gap_refs

    @property
    def has_required_targets(self) -> bool:
        return any(measure.required for measure in self.measures)

    @property
    def required_targets_met(self) -> bool:
        required = tuple(measure for measure in self.measures if measure.required)
        return bool(required) and all(measure.met for measure in required)

    @property
    def unmet_required_axes(self) -> tuple[CoverageAxis, ...]:
        return tuple(
            measure.axis
            for measure in self.measures
            if measure.required and not measure.met
        )


@dataclass(frozen=True)
class SearchBudget:
    max_actions: int | None
    max_cost: float | None
    max_elapsed_ms: float | None
    actions_used: int
    cost_used: float
    elapsed_ms: float

    def __post_init__(self) -> None:
        if self.max_actions is not None and self.max_actions < 1:
            raise ValueError("max_actions must be >= 1 when set")
        if self.max_cost is not None and self.max_cost < 0:
            raise ValueError("max_cost must be >= 0 when set")
        if self.max_elapsed_ms is not None and self.max_elapsed_ms < 0:
            raise ValueError("max_elapsed_ms must be >= 0 when set")
        if self.actions_used < 0 or self.cost_used < 0 or self.elapsed_ms < 0:
            raise ValueError("budget usage values must be >= 0")

    @property
    def action_budget_exhausted(self) -> bool:
        return self.max_actions is not None and self.actions_used >= self.max_actions

    @property
    def cost_budget_exhausted(self) -> bool:
        return self.max_cost is not None and self.cost_used >= self.max_cost

    @property
    def time_budget_exhausted(self) -> bool:
        return self.max_elapsed_ms is not None and self.elapsed_ms >= self.max_elapsed_ms

    @property
    def non_time_budget_exhausted(self) -> bool:
        return self.action_budget_exhausted or self.cost_budget_exhausted


@dataclass(frozen=True)
class SearchProgressSample:
    epoch_index: int
    new_candidates: int
    new_independent_source_roots: int
    new_verified_evidence: int
    material_gap_reduction: int
    coverage_gain: float
    marginal_gain: float
    not_found_count: int = 0

    def __post_init__(self) -> None:
        integer_values = (
            self.epoch_index,
            self.new_candidates,
            self.new_independent_source_roots,
            self.new_verified_evidence,
            self.material_gap_reduction,
            self.not_found_count,
        )
        if any(value < 0 for value in integer_values):
            raise ValueError("progress integer values must be >= 0")
        if self.coverage_gain < 0:
            raise ValueError("coverage_gain must be >= 0")
        if self.marginal_gain < 0:
            raise ValueError("marginal_gain must be >= 0")


@dataclass(frozen=True)
class SaturationPolicy:
    window_size: int = 3
    marginal_gain_threshold: float = 0.0
    minimum_samples: int = 3

    def __post_init__(self) -> None:
        if self.window_size < 1:
            raise ValueError("window_size must be >= 1")
        if self.minimum_samples < self.window_size:
            raise ValueError("minimum_samples must be >= window_size")
        if self.marginal_gain_threshold < 0:
            raise ValueError("marginal_gain_threshold must be >= 0")


@dataclass(frozen=True)
class SaturationState:
    saturated: bool
    recent_gains: tuple[float, ...]
    reason_codes: tuple[str, ...]
    scope_note: str

    def __post_init__(self) -> None:
        if any(gain < 0 for gain in self.recent_gains):
            raise ValueError("recent gains must be >= 0")
        if self.saturated and not self.recent_gains:
            raise ValueError("saturated state requires observed recent gains")
        if not self.scope_note.strip():
            raise ValueError("saturation scope note must be non-empty")


@dataclass(frozen=True)
class UncertaintyState:
    score: float
    material_unknown_refs: tuple[str, ...]
    requires_human_review: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("uncertainty score must be between 0 and 1")


class StopDisposition(StrEnum):
    CONTINUE = "continue"
    REPLAN = "replan"
    STOP = "stop"
    REVIEW = "review"


class StopReason(StrEnum):
    CONTINUE_SEARCH = "CONTINUE_SEARCH"
    NO_MATERIAL_GAP_REMAINS = "NO_MATERIAL_GAP_REMAINS"
    COVERAGE_TARGET_MET = "COVERAGE_TARGET_MET"
    MARGINAL_GAIN_BELOW_THRESHOLD = "MARGINAL_GAIN_BELOW_THRESHOLD"
    SATURATION_REACHED = "SATURATION_REACHED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    TIME_LIMIT_REACHED = "TIME_LIMIT_REACHED"


@dataclass(frozen=True)
class StopPolicy:
    policy_id: str
    coverage_target_is_terminal: bool = False
    allow_saturation_stop: bool = True
    replan_on_low_gain: bool = True


@dataclass(frozen=True)
class StopContext:
    task_id: str
    epoch_id: str
    budget: SearchBudget
    coverage: CoverageState
    saturation: SaturationState
    uncertainty: UncertaintyState
    progress_samples: tuple[SearchProgressSample, ...]
    providers_available: bool | None
    policy_blocked: bool


@dataclass(frozen=True)
class StopEvaluation:
    disposition: StopDisposition
    reason: StopReason
    reason_codes: tuple[str, ...]
    context: StopContext
