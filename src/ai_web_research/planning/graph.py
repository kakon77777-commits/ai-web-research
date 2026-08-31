from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ai_web_research.core.types import ArtifactKind, JsonValue, SearchAction, StopAction


class NodeKind(StrEnum):
    ACTION = "action"
    STOP = "stop"
    JOIN = "join"
    BRANCH = "branch"
    LOOP = "loop"


class EdgeKind(StrEnum):
    NEXT = "next"
    TRUE = "true"
    FALSE = "false"
    SUCCESS = "success"
    FAILURE = "failure"
    LOOP_BACK = "loop_back"


@dataclass(frozen=True)
class ActionNode:
    node_id: str
    action: SearchAction


@dataclass(frozen=True)
class StopNode:
    node_id: str
    stop: StopAction


@dataclass(frozen=True)
class JoinNode:
    node_id: str
    strategy: str


@dataclass(frozen=True)
class BranchNode:
    node_id: str
    condition_ref: str


@dataclass(frozen=True)
class LoopNode:
    node_id: str
    condition_ref: str
    max_iterations: int


PlanNode: TypeAlias = ActionNode | StopNode | JoinNode | BranchNode | LoopNode


@dataclass(frozen=True)
class PlanEdge:
    source: str
    target: str
    kind: EdgeKind
    artifact_kinds: tuple[ArtifactKind, ...]
    condition_ref: str | None = None


@dataclass(frozen=True)
class SearchPlan:
    plan_id: str
    task_id: str
    epoch_id: str
    nodes: tuple[PlanNode, ...]
    edges: tuple[PlanEdge, ...]
    entry_node_ids: tuple[str, ...]
    metadata: dict[str, JsonValue]
