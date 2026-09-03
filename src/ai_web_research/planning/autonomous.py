from __future__ import annotations

from dataclasses import dataclass, replace

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    JsonValue,
    SearchAction,
    SearchState,
    SearchTask,
    StopAction,
    VersionRef,
)
from ai_web_research.methods.corpus import MethodCorpusSnapshot, MethodLifecycle
from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.methods.spec import MethodAvailability, SearchMethodSpec
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.routing.models import RoutingDecision, RoutingPolicy
from ai_web_research.routing.selector import BindingSelector, NoEligibleBinding
from ai_web_research.routing.state import ProviderStateSnapshot

from .autonomous_models import (
    PlanningDecisionSummary,
    PlanningPolicy,
    ProposedMethodStep,
    SearchStrategyProposal,
    planning_budget_from,
    planning_gaps_from_state,
)
from .graph import (
    ActionNode,
    BranchNode,
    EdgeKind,
    JoinNode,
    LoopNode,
    PlanEdge,
    SearchPlan,
    StopNode,
)
from .proposal import RuleProposalSource


@dataclass(frozen=True)
class AutonomousPlanningResult:
    plan: SearchPlan
    proposal: SearchStrategyProposal
    decision_summary: PlanningDecisionSummary


@dataclass(frozen=True)
class _CompiledStep:
    step: ProposedMethodStep
    method_ref: VersionRef
    primary_node: ActionNode
    fallback_node: ActionNode | None
    branch_node: BranchNode | None
    routing_decisions: tuple[RoutingDecision, ...]


class AutonomousPlannerV1:
    planner_id = "planner.autonomous.v1"
    planner_version = "0.4.0"

    def __init__(self, *, proposal_source=None, binding_selector=None) -> None:
        self.proposal_source = proposal_source or RuleProposalSource()
        self.binding_selector = binding_selector or BindingSelector()

    def plan(
        self,
        task: SearchTask,
        state: SearchState,
        methods: MethodRegistrySnapshot,
        corpus: MethodCorpusSnapshot,
        providers: ProviderRegistrySnapshot,
        provider_states: ProviderStateSnapshot,
        routing_policy: RoutingPolicy,
        planning_policy: PlanningPolicy,
        *,
        proposal: SearchStrategyProposal | None = None,
    ) -> AutonomousPlanningResult:
        if task.task_id != state.task_id:
            raise ValueError("task/state task_id mismatch")
        budget = planning_budget_from(task, state)
        gaps = planning_gaps_from_state(state)
        strategy = proposal or self.proposal_source.propose(task, state, gaps, budget)
        if strategy.task_id != task.task_id:
            raise ValueError("proposal/task task_id mismatch")

        compiled: list[_CompiledStep] = []
        selected_method_ids: list[str] = []
        skipped: dict[str, list[str]] = {}
        routing_summaries: list[dict[str, JsonValue]] = []
        action_count = 0
        provider_fallback_count = 0

        for step in strategy.steps[: budget.max_parallel_branches]:
            if action_count >= budget.max_actions:
                for method_id in step.candidate_method_ids:
                    self._skip(skipped, method_id, "ACTION_BUDGET_EXHAUSTED")
                continue

            chosen = None
            chosen_spec = None
            chosen_decision = None
            chosen_inputs: tuple[ArtifactRef, ...] | None = None

            for method_id in step.candidate_method_ids:
                if method_id == "method.query_divergence" and not planning_policy.enable_query_divergence:
                    self._skip(skipped, method_id, "QUERY_DIVERGENCE_DISABLED")
                    continue
                gate = self._method_gate(method_id, corpus, methods, planning_policy)
                if gate[0] is None:
                    self._skip(skipped, method_id, gate[1])
                    continue
                method_ref, spec = gate[0]
                inputs = self._inputs_for_method(spec, task, state)
                if inputs is None:
                    self._skip(skipped, method_id, "NO_COMPATIBLE_INPUT")
                    continue
                try:
                    decision = self.binding_selector.select(
                        method_ref, providers, provider_states, routing_policy
                    )
                except NoEligibleBinding as exc:
                    routing_summaries.append(exc.decision.to_receipt_metadata())
                    self._skip(skipped, method_id, "NO_ELIGIBLE_BINDING")
                    continue
                chosen = method_ref
                chosen_spec = spec
                chosen_decision = decision
                chosen_inputs = inputs
                break

            if chosen is None or chosen_spec is None or chosen_decision is None or chosen_inputs is None:
                continue

            primary = ActionNode(
                node_id=f"{state.epoch_id}:node:{len(compiled) + 1}:primary",
                action=self._action(
                    task=task,
                    state=state,
                    method=chosen_spec,
                    method_ref=chosen,
                    decision=chosen_decision,
                    inputs=chosen_inputs,
                    ordinal=action_count + 1,
                    role="primary",
                ),
            )
            action_count += 1
            routing_summaries.append(chosen_decision.to_receipt_metadata())

            fallback_node = None
            branch_node = None
            routing_decisions = [chosen_decision]
            if (
                planning_policy.enable_provider_fallback
                and provider_fallback_count < budget.max_provider_fallbacks
                and action_count < budget.max_actions
            ):
                fallback_binding_ids = tuple(
                    candidate.binding_id
                    for candidate in chosen_decision.candidates
                    if candidate.eligible and candidate.binding_id != chosen_decision.selected_binding_id
                )
                if fallback_binding_ids:
                    fallback_policy = replace(
                        routing_policy,
                        policy_id=f"{routing_policy.policy_id}:fallback:{step.step_id}",
                        preferred_binding_ids=fallback_binding_ids,
                    )
                    try:
                        fallback_decision = self.binding_selector.select(
                            chosen, providers, provider_states, fallback_policy
                        )
                    except NoEligibleBinding:
                        fallback_decision = None
                else:
                    fallback_decision = None
                if fallback_decision is not None:
                    fallback_node = ActionNode(
                        node_id=f"{state.epoch_id}:node:{len(compiled) + 1}:fallback",
                        action=self._action(
                            task=task,
                            state=state,
                            method=chosen_spec,
                            method_ref=chosen,
                            decision=fallback_decision,
                            inputs=chosen_inputs,
                            ordinal=action_count + 1,
                            role="provider_fallback",
                        ),
                    )
                    action_count += 1
                    provider_fallback_count += 1
                    branch_node = BranchNode(
                        node_id=f"{state.epoch_id}:node:{len(compiled) + 1}:branch",
                        condition_ref=f"{primary.action.action_id}:failed_or_empty",
                    )
                    routing_decisions.append(fallback_decision)
                    routing_summaries.append(fallback_decision.to_receipt_metadata())

            compiled.append(
                _CompiledStep(
                    step=step,
                    method_ref=chosen,
                    primary_node=primary,
                    fallback_node=fallback_node,
                    branch_node=branch_node,
                    routing_decisions=tuple(routing_decisions),
                )
            )
            if chosen.id not in selected_method_ids:
                selected_method_ids.append(chosen.id)

        if not compiled:
            reason = (
                "NO_ELIGIBLE_BINDING"
                if any("NO_ELIGIBLE_BINDING" in reasons for reasons in skipped.values())
                else "NO_EXECUTION_READY_METHOD"
            )
            stop = StopNode(
                node_id=f"{state.epoch_id}:node:stop",
                stop=StopAction(
                    action_id=f"{state.epoch_id}:stop:1",
                    task_id=task.task_id,
                    epoch_id=state.epoch_id,
                    reason=reason,
                    state_ref=state.epoch_id,
                    created_by=self.planner_id,
                    created_at=state.planned_at,
                ),
            )
            summary = self._summary(
                strategy, corpus, provider_states, selected_method_ids, skipped,
                routing_summaries, gaps, budget,
            )
            plan = SearchPlan(
                plan_id=f"{state.epoch_id}:plan:autonomous:1",
                task_id=task.task_id,
                epoch_id=state.epoch_id,
                nodes=(stop,),
                edges=(),
                entry_node_ids=(stop.node_id,),
                metadata=self._plan_metadata(summary, strategy),
            )
            return AutonomousPlanningResult(plan=plan, proposal=strategy, decision_summary=summary)

        nodes: list = []
        edges: list[PlanEdge] = []
        entry_node_ids: list[str] = []
        join = JoinNode(node_id=f"{state.epoch_id}:node:join", strategy="all_available_branches")

        for item in compiled:
            nodes.append(item.primary_node)
            entry_node_ids.append(item.primary_node.node_id)
            if item.branch_node is not None and item.fallback_node is not None:
                nodes.extend((item.branch_node, item.fallback_node))
                edges.extend((
                    PlanEdge(item.primary_node.node_id, item.branch_node.node_id, EdgeKind.NEXT, ()),
                    PlanEdge(item.branch_node.node_id, item.fallback_node.node_id, EdgeKind.TRUE, (), item.branch_node.condition_ref),
                    PlanEdge(item.branch_node.node_id, join.node_id, EdgeKind.FALSE, (), item.branch_node.condition_ref),
                    PlanEdge(item.fallback_node.node_id, join.node_id, EdgeKind.SUCCESS, ()),
                ))
            else:
                edges.append(PlanEdge(item.primary_node.node_id, join.node_id, EdgeKind.NEXT, ()))

        nodes.append(join)
        stop = StopNode(
            node_id=f"{state.epoch_id}:node:stop",
            stop=StopAction(
                action_id=f"{state.epoch_id}:stop:1",
                task_id=task.task_id,
                epoch_id=state.epoch_id,
                reason="EPOCH_COMPLETE_OR_REPLAN",
                state_ref=state.epoch_id,
                created_by=self.planner_id,
                created_at=state.planned_at,
            ),
        )

        loop_iterations = min(budget.max_loop_iterations, strategy.max_replans + 1)
        if strategy.replan_condition_ref and strategy.max_replans > 0 and loop_iterations > 1:
            loop = LoopNode(
                node_id=f"{state.epoch_id}:node:replan-loop",
                condition_ref=strategy.replan_condition_ref,
                max_iterations=loop_iterations,
            )
            nodes.extend((loop, stop))
            edges.append(PlanEdge(join.node_id, loop.node_id, EdgeKind.NEXT, ()))
            for entry in entry_node_ids:
                edges.append(
                    PlanEdge(loop.node_id, entry, EdgeKind.LOOP_BACK, (), strategy.replan_condition_ref)
                )
            edges.append(
                PlanEdge(loop.node_id, stop.node_id, EdgeKind.FALSE, (), strategy.replan_condition_ref)
            )
        else:
            nodes.append(stop)
            edges.append(PlanEdge(join.node_id, stop.node_id, EdgeKind.NEXT, ()))

        summary = self._summary(
            strategy, corpus, provider_states, selected_method_ids, skipped,
            routing_summaries, gaps, budget,
        )
        plan = SearchPlan(
            plan_id=f"{state.epoch_id}:plan:autonomous:1",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            nodes=tuple(nodes),
            edges=tuple(edges),
            entry_node_ids=tuple(entry_node_ids),
            metadata=self._plan_metadata(summary, strategy),
        )
        return AutonomousPlanningResult(plan=plan, proposal=strategy, decision_summary=summary)

    @staticmethod
    def _skip(skipped: dict[str, list[str]], method_id: str, reason: str) -> None:
        reasons = skipped.setdefault(method_id, [])
        if reason not in reasons:
            reasons.append(reason)

    @staticmethod
    def _method_gate(
        method_id: str,
        corpus: MethodCorpusSnapshot,
        methods: MethodRegistrySnapshot,
        planning_policy: PlanningPolicy,
    ) -> tuple[tuple[VersionRef, SearchMethodSpec] | None, str]:
        try:
            entry = corpus.get(method_id)
        except KeyError:
            return None, "METHOD_NOT_IN_CORPUS"
        if entry.lifecycle is MethodLifecycle.DOCUMENTED:
            return None, "LIFECYCLE_DOCUMENTED"
        if entry.lifecycle is MethodLifecycle.DEPRECATED:
            return None, "LIFECYCLE_DEPRECATED"
        if entry.lifecycle is MethodLifecycle.EXPERIMENTAL and not planning_policy.allow_experimental:
            return None, "EXPERIMENTAL_METHOD_NOT_ALLOWED"
        if entry.spec_ref is None:
            return None, "NO_RUNTIME_SPEC"
        try:
            spec = methods.get(entry.spec_ref)
        except KeyError:
            return None, "RUNTIME_SPEC_NOT_REGISTERED"
        if spec.availability in {MethodAvailability.UNAVAILABLE, MethodAvailability.DEPRECATED}:
            return None, "RUNTIME_METHOD_UNAVAILABLE"
        return (entry.spec_ref, spec), "OK"

    @staticmethod
    def _inputs_for_method(
        method: SearchMethodSpec,
        task: SearchTask,
        state: SearchState,
    ) -> tuple[ArtifactRef, ...] | None:
        accepted = method.input_contract.accepts
        selected = tuple(
            artifact for artifact in state.active_artifacts if artifact.kind in accepted
        )
        if selected:
            return selected
        if ArtifactKind.QUERY in accepted:
            return (ArtifactRef(ArtifactKind.QUERY, f"{task.task_id}:query:0"),)
        if ArtifactKind.CANDIDATE in accepted and state.candidate_refs:
            return tuple(ArtifactRef(ArtifactKind.CANDIDATE, ref) for ref in state.candidate_refs)
        if ArtifactKind.DOCUMENT_REF in accepted:
            refs = tuple(
                artifact for artifact in state.active_artifacts if artifact.kind is ArtifactKind.DOCUMENT_REF
            )
            if refs:
                return refs
        return None

    def _action(
        self,
        *,
        task: SearchTask,
        state: SearchState,
        method: SearchMethodSpec,
        method_ref: VersionRef,
        decision: RoutingDecision,
        inputs: tuple[ArtifactRef, ...],
        ordinal: int,
        role: str,
    ) -> SearchAction:
        if decision.selected_provider_ref is None or decision.selected_surface_id is None or decision.selected_binding_id is None:
            raise ValueError("routing decision has no selected binding")
        return SearchAction(
            action_id=f"{state.epoch_id}:action:{ordinal}",
            task_id=task.task_id,
            epoch_id=state.epoch_id,
            method_ref=method_ref,
            provider_ref=decision.selected_provider_ref,
            surface_id=decision.selected_surface_id,
            binding_id=decision.selected_binding_id,
            action_kind=self._action_kind(method.method_id),
            inputs=inputs,
            parameters=self._parameters(method, task),
            guards=(),
            expected_effects=tuple(method.postconditions) or ("method_effect_observed",),
            created_by=self.planner_id,
            created_at=state.planned_at,
        )

    @staticmethod
    def _action_kind(method_id: str) -> ActionKind:
        if method_id == "method.identity_search":
            return ActionKind.RESOLVE_IDENTITY
        if method_id == "method.query_divergence":
            return ActionKind.QUERY_TRANSFORM
        if method_id == "method.fetch_document":
            return ActionKind.FETCH
        if method_id == "method.extract_candidate_evidence":
            return ActionKind.EXTRACT
        if method_id == "method.crawl_discovery":
            return ActionKind.CRAWL
        return ActionKind.SEARCH

    @staticmethod
    def _parameters(method: SearchMethodSpec, task: SearchTask) -> dict[str, JsonValue]:
        required = method.parameter_schema.get("required", []) if isinstance(method.parameter_schema, dict) else []
        parameters: dict[str, JsonValue] = {}
        if "query" in required:
            parameters["query"] = task.raw_request
        return parameters

    @staticmethod
    def _summary(
        proposal: SearchStrategyProposal,
        corpus: MethodCorpusSnapshot,
        provider_states: ProviderStateSnapshot,
        selected_method_ids: list[str],
        skipped: dict[str, list[str]],
        routing_summaries: list[dict[str, JsonValue]],
        gaps,
        budget,
    ) -> PlanningDecisionSummary:
        return PlanningDecisionSummary(
            proposal_id=proposal.proposal_id,
            method_corpus_snapshot_id=corpus.snapshot_id,
            provider_state_snapshot_id=provider_states.snapshot_id,
            selected_method_ids=tuple(selected_method_ids),
            skipped_method_ids=tuple(skipped),
            skip_reasons=tuple((method_id, tuple(reasons)) for method_id, reasons in skipped.items()),
            routing_summaries=tuple(routing_summaries),
            gap_refs=tuple(gap.gap_ref for gap in gaps),
            budget=budget,
        )

    def _plan_metadata(
        self,
        summary: PlanningDecisionSummary,
        proposal: SearchStrategyProposal,
    ) -> dict[str, JsonValue]:
        return {
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
            "proposal_id": proposal.proposal_id,
            "method_corpus_snapshot_id": summary.method_corpus_snapshot_id,
            "provider_state_snapshot_id": summary.provider_state_snapshot_id,
            "selected_method_ids": list(summary.selected_method_ids),
            "skipped_method_ids": list(summary.skipped_method_ids),
            "gap_refs": list(summary.gap_refs),
            "budget": {
                "max_actions": summary.budget.max_actions,
                "max_parallel_branches": summary.budget.max_parallel_branches,
                "max_loop_iterations": summary.budget.max_loop_iterations,
                "max_provider_fallbacks": summary.budget.max_provider_fallbacks,
            },
            "proposal_reason_codes": list(proposal.reason_codes),
            "reasoning_omitted": True,
        }
