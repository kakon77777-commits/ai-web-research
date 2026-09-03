from __future__ import annotations

from ai_web_research.core.types import ArtifactKind, SearchIntent, SearchState, SearchTask
from .autonomous_models import PlanningBudget, PlanningGap, ProposedMethodStep, SearchStrategyProposal


class RuleProposalSource:
    proposer_id = "planner.proposal.rule.v1"
    proposer_version = "0.4.0"

    def propose(
        self,
        task: SearchTask,
        state: SearchState,
        gaps: tuple[PlanningGap, ...],
        budget: PlanningBudget,
    ) -> SearchStrategyProposal:
        steps: list[ProposedMethodStep] = []
        seen_objectives: set[str] = set()

        def add(objective: str, methods: tuple[str, ...], *reasons: str) -> None:
            if objective in seen_objectives or len(steps) >= budget.max_actions:
                return
            seen_objectives.add(objective)
            steps.append(
                ProposedMethodStep(
                    step_id=f"step-{len(steps) + 1}:{objective}",
                    objective=objective,
                    candidate_method_ids=methods,
                    reason_codes=tuple(reasons),
                )
            )

        for gap in sorted(gaps, key=lambda item: (-item.priority, item.gap_ref)):
            if gap.gap_type == "identity_unresolved":
                add("resolve_identity", ("method.identity_search",), "GAP_IDENTITY_UNRESOLVED", gap.gap_ref)
            elif gap.gap_type == "counter_evidence":
                add(
                    "find_counter_evidence",
                    ("method.counter_evidence_search", "method.lexical_search"),
                    "GAP_COUNTER_EVIDENCE",
                    gap.gap_ref,
                )
            elif gap.gap_type == "candidate_acquisition" and state.candidate_refs:
                add("acquire_candidate", ("method.fetch_document",), "GAP_CANDIDATE_ACQUISITION", gap.gap_ref)
            elif gap.gap_type == "evidence_missing" and any(
                artifact.kind is ArtifactKind.DOCUMENT for artifact in state.active_artifacts
            ):
                add("extract_evidence", ("method.extract_candidate_evidence",), "GAP_EVIDENCE_MISSING", gap.gap_ref)
            elif gap.gap_type in {"source_independence", "candidate_discovery", "source_coverage"}:
                add("discover_candidates", ("method.lexical_search",), "GAP_DISCOVERY", gap.gap_ref)

        if task.intent is SearchIntent.RESOLVE_IDENTITY:
            add("resolve_identity", ("method.identity_search",), "TASK_RESOLVE_IDENTITY")
        elif task.intent in {SearchIntent.DISCOVER, SearchIntent.RESEARCH, SearchIntent.COMPARE}:
            add("discover_candidates", ("method.lexical_search",), f"TASK_{task.intent.value.upper()}")
            if budget.max_parallel_branches >= 2:
                add("diversify_queries", ("method.query_divergence",), "PARALLEL_QUERY_DIVERGENCE")
        elif task.intent is SearchIntent.FALSIFY:
            add(
                "find_counter_evidence",
                ("method.counter_evidence_search", "method.lexical_search"),
                "TASK_FALSIFY",
            )
        elif task.intent is SearchIntent.VERIFY:
            if any(artifact.kind is ArtifactKind.DOCUMENT for artifact in state.active_artifacts):
                add("extract_evidence", ("method.extract_candidate_evidence",), "TASK_VERIFY")
            elif state.candidate_refs:
                add("acquire_candidate", ("method.fetch_document",), "TASK_VERIFY_ACQUIRE")
        elif task.intent is SearchIntent.LOCATE:
            add("discover_candidates", ("method.lexical_search",), "TASK_LOCATE")

        open_gap_reason = ("OPEN_GAPS",) if gaps else ()
        return SearchStrategyProposal(
            proposal_id=f"{state.epoch_id}:strategy:1",
            task_id=task.task_id,
            steps=tuple(steps),
            replan_condition_ref="open_gaps_remain" if gaps and budget.max_loop_iterations > 1 else None,
            max_replans=(budget.max_loop_iterations - 1) if gaps and budget.max_loop_iterations > 1 else 0,
            reason_codes=(f"PROPOSER_{self.proposer_id}", *open_gap_reason),
        )
