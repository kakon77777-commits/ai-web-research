from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.policy.models import PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot

from .candidate_verification import (
    CandidateFetchStatus,
    CandidateFetchUnavailable,
    CandidateFetchExecution,
    compile_candidate_fetch_action,
    execute_candidate_fetch_action,
    select_fetch_binding,
)
from .fetched_page import FetchedPage
from .models import SourceFamilyResolution, SourceNode, SourceRelation
from .predecessor_verification import (
    PredecessorVerification,
    _normalize_url,
    verify_predecessor_candidate,
)
from .family import resolve_source_families
from .trace import ReverseTracePlan, TraceActionKind
from .trace_execution import TraceExecutionBatch, TraceExecutionStatus


@dataclass(frozen=True)
class CandidateVerificationRecord:
    source_id: str
    trace_action_id: str
    candidate: DiscoveryCandidate
    fetch: CandidateFetchExecution
    verification: PredecessorVerification | None


@dataclass(frozen=True)
class CandidateVerificationBatch:
    source_id: str
    records: tuple[CandidateVerificationRecord, ...]
    complete: bool
    truncated: bool


@dataclass(frozen=True)
class VerifiedTraceGraphUpdate:
    batches: tuple[CandidateVerificationBatch, ...]
    candidate_source_nodes: tuple[SourceNode, ...]
    verified_relations: tuple[SourceRelation, ...]
    source_relations: tuple[SourceRelation, ...]
    family_resolution: SourceFamilyResolution
    independent_root_count_before: int
    independent_root_count_after: int


def _direct_candidate(source_id: str, action) -> DiscoveryCandidate:
    digest = sha256(f"{source_id}|{action.action_id}|{action.url}".encode("utf-8")).hexdigest()[:20]
    return DiscoveryCandidate(
        candidate_id=f"direct-trace-candidate:{digest}",
        url=str(action.url),
        title=None,
        snippet=None,
        provider_id="trace.direct",
        surface_id="source_signal",
        provider_rank=0,
        artifact_ids=(action.action_id,),
        metadata={"evidence_role":"discovery_only","trace_origin":"direct_predecessor"},
    )


def _candidate_node(page: FetchedPage) -> SourceNode:
    return SourceNode(
        source_id=page.source_id,
        url=page.url,
        canonical_url=page.canonical_url,
        published_at=page.published_at,
        observed_at=page.observed_at,
        owner_hint=None,
        content_hash=page.content_hash,
        metadata={"verification_fetch": True},
    )


async def verify_trace_candidate_batches(
    *,
    source_page_results: tuple[Any, ...],
    trace_plans: dict[str, ReverseTracePlan],
    trace_execution_batches: tuple[TraceExecutionBatch, ...],
    source_nodes: tuple[SourceNode, ...],
    source_relations: tuple[SourceRelation, ...],
    tracked_source_ids: tuple[str, ...],
    providers: ProviderRegistrySnapshot,
    trusted_runtime: Any,
    execution_context: ExecutionContext,
    policy_context: PolicyContext,
    reader: Callable[[str], str],
    task_id: str,
    epoch_id: str,
    created_at: str,
    provider_preferences: tuple[str, ...] = (),
    credential_profile_id: str | None = None,
    max_candidates_per_execution: int = 3,
    max_total_candidate_fetches: int = 8,
) -> VerifiedTraceGraphUpdate:
    if max_candidates_per_execution < 1 or max_total_candidate_fetches < 1:
        raise ValueError("candidate fetch limits must be positive")
    page_by_source = {item.page.source_id: item for item in source_page_results}
    batch_by_source = {batch.source_id: batch for batch in trace_execution_batches}
    before_resolution = resolve_source_families(source_nodes, source_relations)
    before_count = before_resolution.independent_root_count(tracked_source_ids)

    try:
        binding = select_fetch_binding(providers, provider_preferences)
    except CandidateFetchUnavailable:
        return VerifiedTraceGraphUpdate(
            batches=tuple(CandidateVerificationBatch(source_id, (), False, False) for source_id in sorted(trace_plans)),
            candidate_source_nodes=(),
            verified_relations=(),
            source_relations=source_relations,
            family_resolution=before_resolution,
            independent_root_count_before=before_count,
            independent_root_count_after=before_count,
        )

    total_used = 0
    output_batches: list[CandidateVerificationBatch] = []
    candidate_nodes: dict[str, SourceNode] = {}
    verified_relations: dict[str, SourceRelation] = {}

    for source_id in sorted(trace_plans):
        source_page_result = page_by_source.get(source_id)
        plan = trace_plans[source_id]
        if source_page_result is None:
            output_batches.append(CandidateVerificationBatch(source_id, (), False, False))
            continue

        requests: list[tuple[str, DiscoveryCandidate]] = []
        for action in plan.actions:
            if action.kind is TraceActionKind.DIRECT_PREDECESSOR and action.url:
                requests.append((action.action_id, _direct_candidate(source_id, action)))

        trace_batch = batch_by_source.get(source_id)
        if trace_batch is not None:
            for execution in trace_batch.executions:
                if execution.status is not TraceExecutionStatus.SUCCEEDED or execution.discovery_batch is None:
                    continue
                candidates = sorted(
                    execution.discovery_batch.candidates,
                    key=lambda c: (c.provider_rank, c.url, c.candidate_id),
                )[:max_candidates_per_execution]
                requests.extend((execution.trace_action_id, candidate) for candidate in candidates)

        deduped: list[tuple[str, DiscoveryCandidate]] = []
        seen_urls: set[str] = set()
        for trace_action_id, candidate in requests:
            normalized = _normalize_url(candidate.url) or candidate.url
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            deduped.append((trace_action_id, candidate))

        records: list[CandidateVerificationRecord] = []
        truncated = False
        for trace_action_id, candidate in deduped:
            if total_used >= max_total_candidate_fetches:
                truncated = True
                break
            total_used += 1
            compiled = compile_candidate_fetch_action(
                source_id=source_id,
                trace_action_id=trace_action_id,
                candidate=candidate,
                binding=binding,
                task_id=task_id,
                epoch_id=epoch_id,
                created_at=created_at,
            )
            fetch = await execute_candidate_fetch_action(
                compiled,
                trusted_runtime=trusted_runtime,
                execution_context=execution_context,
                policy_context=policy_context,
                reader=reader,
                credential_profile_id=credential_profile_id,
                fail_fast=False,
            )
            verification = None
            if fetch.status is CandidateFetchStatus.FETCHED and fetch.fetched_page is not None:
                verification = verify_predecessor_candidate(source_page_result, fetch)
                node = _candidate_node(fetch.fetched_page)
                candidate_nodes[node.source_id] = node
                if verification.relation is not None:
                    verified_relations[verification.relation.relation_id] = verification.relation
            records.append(CandidateVerificationRecord(source_id, trace_action_id, candidate, fetch, verification))

        complete = (
            not truncated
            and all(record.fetch.status is CandidateFetchStatus.FETCHED for record in records)
            and (trace_batch.complete if trace_batch is not None else True)
        )
        output_batches.append(CandidateVerificationBatch(source_id, tuple(records), complete, truncated))

    node_map = {node.source_id: node for node in source_nodes}
    node_map.update(candidate_nodes)
    relation_map = {relation.relation_id: relation for relation in source_relations}
    relation_map.update(verified_relations)
    updated_nodes = tuple(node_map[key] for key in sorted(node_map))
    updated_relations = tuple(relation_map[key] for key in sorted(relation_map))
    after_resolution = resolve_source_families(updated_nodes, updated_relations)
    after_count = after_resolution.independent_root_count(tracked_source_ids)
    return VerifiedTraceGraphUpdate(
        batches=tuple(output_batches),
        candidate_source_nodes=tuple(candidate_nodes[key] for key in sorted(candidate_nodes)),
        verified_relations=tuple(verified_relations[key] for key in sorted(verified_relations)),
        source_relations=updated_relations,
        family_resolution=after_resolution,
        independent_root_count_before=before_count,
        independent_root_count_after=after_count,
    )
