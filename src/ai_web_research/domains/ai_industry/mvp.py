from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.domains.ai_industry.daily import (
    DailyBatch,
    DailyEventInput,
    DailySelectionPolicy,
    select_daily_batch,
)
from ai_web_research.knowledge.models import CanonicalClaim, CanonicalEvent, ClaimOrigin, KnowledgeState
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.projection.daily import render_machine_daily, render_zh_hant_daily
from ai_web_research.projection.models import ProjectionArtifact
from ai_web_research.projection.registry import ArtifactRegistry
from ai_web_research.resource_control.models import ResearchBudget


@dataclass(frozen=True)
class AIDailyMVPResult:
    batch: DailyBatch
    machine_projection: dict
    zh_hant_artifact: ProjectionArtifact
    artifact_registry: ArtifactRegistry
    upstream_failures: tuple[str, ...]


def build_ai_daily_mvp(
    *,
    store: KnowledgeStore,
    batch_id: str,
    claims: tuple[CanonicalClaim, ...],
    events: tuple[CanonicalEvent, ...],
    state: KnowledgeState,
    candidates: tuple[DailyEventInput, ...],
    budget: ResearchBudget,
    policy: DailySelectionPolicy,
    generated_at: str,
    artifact_id: str,
    upstream_failures: tuple[str, ...] = (),
) -> AIDailyMVPResult:
    claims_by_id = {claim.claim_id: claim for claim in claims}
    events_by_id = {event.event_id: event for event in events}

    for claim in claims:
        if claim.claim_origin is ClaimOrigin.SOURCE_ASSERTION and not claim.evidence_ids:
            raise ValueError(f"source assertion requires evidence: {claim.claim_id}")
        store.save_claim(claim)

    for event in events:
        missing_claims = tuple(claim_id for claim_id in event.claim_ids if claim_id not in claims_by_id)
        if missing_claims:
            raise ValueError(f"event {event.event_id} references missing claims {missing_claims}")
        store.save_event(event)

    missing_state_claims = tuple(claim_id for claim_id in state.claim_ids if claim_id not in claims_by_id)
    missing_state_events = tuple(event_id for event_id in state.event_ids if event_id not in events_by_id)
    if missing_state_claims or missing_state_events:
        raise ValueError(
            f"knowledge state references missing objects: claims={missing_state_claims}, events={missing_state_events}"
        )
    store.save_knowledge_state(state)

    batch = select_daily_batch(
        batch_id=batch_id,
        state=state,
        candidates=candidates,
        budget=budget,
        policy=policy,
        generated_at=generated_at,
    )
    machine = render_machine_daily(batch=batch, events=events_by_id, claims=claims_by_id)
    zh = render_zh_hant_daily(
        artifact_id=artifact_id,
        batch=batch,
        events=events_by_id,
        claims=claims_by_id,
        generated_at=generated_at,
    )
    registry = ArtifactRegistry()
    registry.register(zh)

    return AIDailyMVPResult(
        batch=batch,
        machine_projection=machine,
        zh_hant_artifact=zh,
        artifact_registry=registry,
        upstream_failures=tuple(upstream_failures),
    )
