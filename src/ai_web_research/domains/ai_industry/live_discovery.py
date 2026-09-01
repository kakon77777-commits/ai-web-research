from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.discovery.models import DiscoveryBatch
from ai_web_research.discovery.normalize import normalize_discovery_observation
from ai_web_research.execution.models import ProviderObservation
from ai_web_research.knowledge.models import CanonicalClaim, CanonicalEvent, KnowledgeState
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.resource_control.models import ResearchBudget
from ai_web_research.source_graph.family import resolve_source_families
from ai_web_research.source_graph.models import SourceFamilyResolution, SourceNode, SourceRelation
from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.page_signals import PageSignalExtraction
from ai_web_research.source_graph.html_extract import extract_page_source_signals
from ai_web_research.source_graph.signal_compile import CompiledPageSourceSignals, compile_page_source_signals
from ai_web_research.source_graph.trace import (
    ReverseTracePlan,
    SourceTraceSignals,
    materialize_explicit_trace_edges,
    plan_reverse_trace,
)

from .canonicalize import canonicalize_event, promote_claim
from .daily import DailyEventInput, DailySelectionPolicy
from .models import ClaimDraft, EventDraft
from .mvp import AIDailyMVPResult, build_ai_daily_mvp
from .source_independence import attach_independent_root_count


@dataclass(frozen=True)
class FetchedSourcePageResult:
    page: FetchedPage
    extraction: PageSignalExtraction
    compiled: CompiledPageSourceSignals


@dataclass(frozen=True)
class AIDailyFetchedSourceResult:
    discovery_result: "AIDailyDiscoveryResult"
    page_results: tuple[FetchedSourcePageResult, ...]


@dataclass(frozen=True)
class AIDailyDiscoveryResult:
    discovery_batch: DiscoveryBatch
    trace_plans: dict[str, ReverseTracePlan]
    source_relations: tuple[SourceRelation, ...]
    family_resolution: SourceFamilyResolution
    canonical_claim: CanonicalClaim
    canonical_event: CanonicalEvent
    mvp_result: AIDailyMVPResult


def build_ai_daily_from_discovery(
    *,
    store: KnowledgeStore,
    batch_id: str,
    observation: ProviderObservation,
    source_nodes: tuple[SourceNode, ...],
    base_relations: tuple[SourceRelation, ...],
    trace_signals_by_source: dict[str, SourceTraceSignals],
    claim_draft: ClaimDraft,
    evidence_source_ids: tuple[str, ...],
    event_draft: EventDraft,
    state: KnowledgeState,
    budget: ResearchBudget,
    policy: DailySelectionPolicy,
    generated_at: str,
    artifact_id: str,
    importance: float,
    freshness: float,
    audience_relevance: float,
    confidence: float,
    materialize_trace_edges: bool = True,
) -> AIDailyDiscoveryResult:
    discovery_batch = normalize_discovery_observation(observation)
    node_by_id = {node.source_id: node for node in source_nodes}

    trace_plans: dict[str, ReverseTracePlan] = {}
    traced_relations: list[SourceRelation] = []
    for source_id in sorted(trace_signals_by_source):
        signals = trace_signals_by_source[source_id]
        trace_plans[source_id] = plan_reverse_trace(source_id, signals)
        source = node_by_id.get(source_id)
        if source is None:
            continue
        if materialize_trace_edges:
            traced_relations.extend(
                materialize_explicit_trace_edges(
                    source,
                    discovery_batch.candidates,
                    signals,
                )
            )

    relations = tuple(base_relations) + tuple(traced_relations)
    family_resolution = resolve_source_families(source_nodes, relations)
    resolved_draft = attach_independent_root_count(
        claim_draft,
        evidence_source_ids,
        family_resolution,
    )
    canonical_claim = promote_claim(resolved_draft)
    canonical_event = canonicalize_event(event_draft)

    daily_candidate = DailyEventInput(
        event=canonical_event,
        claims=(canonical_claim,),
        importance=importance,
        freshness=freshness,
        audience_relevance=audience_relevance,
        confidence=confidence,
    )
    mvp_result = build_ai_daily_mvp(
        store=store,
        batch_id=batch_id,
        claims=(canonical_claim,),
        events=(canonical_event,),
        state=state,
        candidates=(daily_candidate,),
        budget=budget,
        policy=policy,
        generated_at=generated_at,
        artifact_id=artifact_id,
    )
    return AIDailyDiscoveryResult(
        discovery_batch=discovery_batch,
        trace_plans=trace_plans,
        source_relations=relations,
        family_resolution=family_resolution,
        canonical_claim=canonical_claim,
        canonical_event=canonical_event,
        mvp_result=mvp_result,
    )


def build_ai_daily_from_fetched_pages(
    *,
    store: KnowledgeStore,
    batch_id: str,
    observation: ProviderObservation,
    fetched_pages: tuple[FetchedPage, ...],
    source_nodes: tuple[SourceNode, ...],
    claim_keywords: tuple[str, ...],
    claim_draft: ClaimDraft,
    evidence_source_ids: tuple[str, ...],
    event_draft: EventDraft,
    state: KnowledgeState,
    budget: ResearchBudget,
    policy: DailySelectionPolicy,
    generated_at: str,
    artifact_id: str,
    importance: float,
    freshness: float,
    audience_relevance: float,
    confidence: float,
    base_relations: tuple[SourceRelation, ...] = (),
) -> AIDailyFetchedSourceResult:
    page_results: list[FetchedSourcePageResult] = []
    trace_signals_by_source: dict[str, SourceTraceSignals] = {}
    compiled_relations: list[SourceRelation] = list(base_relations)

    for page in fetched_pages:
        extraction = extract_page_source_signals(page)
        compiled = compile_page_source_signals(
            page, extraction, claim_keywords=claim_keywords
        )
        page_results.append(
            FetchedSourcePageResult(page=page, extraction=extraction, compiled=compiled)
        )
        trace_signals_by_source[page.source_id] = compiled.trace_signals
        compiled_relations.extend(compiled.relations)

    discovery_result = build_ai_daily_from_discovery(
        store=store,
        batch_id=batch_id,
        observation=observation,
        source_nodes=source_nodes,
        base_relations=tuple(compiled_relations),
        trace_signals_by_source=trace_signals_by_source,
        claim_draft=claim_draft,
        evidence_source_ids=evidence_source_ids,
        event_draft=event_draft,
        state=state,
        budget=budget,
        policy=policy,
        generated_at=generated_at,
        artifact_id=artifact_id,
        importance=importance,
        freshness=freshness,
        audience_relevance=audience_relevance,
        confidence=confidence,
        materialize_trace_edges=False,
    )
    return AIDailyFetchedSourceResult(
        discovery_result=discovery_result,
        page_results=tuple(page_results),
    )
