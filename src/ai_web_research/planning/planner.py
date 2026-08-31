from __future__ import annotations

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    SearchAction,
    SearchIntent,
    SearchState,
    SearchTask,
    VersionRef,
)
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from .graph import ActionNode, SearchPlan


class PlanningError(RuntimeError):
    pass


class DeterministicPlanner:
    planner_id = "planner.rule.v0"
    planner_version = "0.1.0"

    async def plan(
        self,
        task: SearchTask,
        state: SearchState,
        methods: MethodRegistrySnapshot,
        providers: ProviderRegistrySnapshot,
        experience=None,
    ) -> SearchPlan:
        if task.intent is not SearchIntent.RESOLVE_IDENTITY:
            raise PlanningError(f"unsupported intent: {task.intent}")

        method = next((m for m in methods.methods if m.method_id == "method.identity_search" and m.version == "1.0.0"), None)
        if method is None:
            raise PlanningError("identity search method is not registered")
        method_ref = VersionRef(method.method_id, method.version)
        binding = next(
            (
                b for b in providers.bindings
                if b.enabled and b.method_ref == method_ref and b.provider_ref.id == "provider.local_corpus"
            ),
            None,
        )
        if binding is None:
            raise PlanningError("identity search local-corpus binding is not registered")

        action = SearchAction(
            action_id=f"{state.epoch_id}:action:1",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            method_ref=method_ref,
            provider_ref=binding.provider_ref,
            surface_id=binding.surface_id,
            binding_id=binding.binding_id,
            action_kind=ActionKind.RESOLVE_IDENTITY,
            inputs=(ArtifactRef(kind=ArtifactKind.QUERY, id=f"{task.task_id}:query:0"),),
            parameters={"query": task.raw_request},
            guards=(),
            expected_effects=("candidate_set_created",),
            created_by=self.planner_id,
            created_at="1970-01-01T00:00:00+00:00",
        )
        node = ActionNode(node_id=f"{state.epoch_id}:node:1", action=action)
        return SearchPlan(
            plan_id=f"{state.epoch_id}:plan:1",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            nodes=(node,),
            edges=(),
            entry_node_ids=(node.node_id,),
            metadata={"planner_id": self.planner_id, "planner_version": self.planner_version},
        )
