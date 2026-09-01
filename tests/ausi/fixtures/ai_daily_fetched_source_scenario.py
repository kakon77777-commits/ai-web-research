from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.domains.ai_industry.daily import DailySelectionPolicy
from ai_web_research.domains.ai_industry.models import AIEventType, ClaimDraft, EventDraft
from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.execution.models import ObservationStatus, ProviderObservation
from ai_web_research.knowledge.models import ClaimOrigin, ClaimState, EventStatus, KnowledgeMode, KnowledgeState, ValidTime
from ai_web_research.resource_control.models import ResearchBudget
from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.models import SourceNode

NOW = "2026-09-01T16:00:00Z"


def source_id(url: str) -> str:
    return f"source:{url.rstrip('/')}"


def evidence(eid: str, source_url: str) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_evidence_id=eid, acquired_asset_id=f"asset:{eid}", field_name="key_claim",
        extracted_value="Model X was released.", source_identity_ref=source_id(source_url),
        work_identity_ref=None, version_identity_ref=None, manifestation_identity_ref=None,
        anchor_refs=(f"anchor:{eid}",), extraction_method="fixture_trusted_extractor",
        extractor_version="fixture-v1", model_ref=None, source_type="fetched_anchored_source",
        usage_envelope_id="usage:fixture", extractor_confidence=1.0,
        semantic_support_verified=False, validation_notes=(), created_at=NOW,
    )


@dataclass(frozen=True)
class FetchedSourceScenario:
    observation: ProviderObservation
    fetched_pages: tuple[FetchedPage, ...]
    source_nodes: tuple[SourceNode, ...]
    claim_draft: ClaimDraft
    evidence_source_ids: tuple[str, ...]
    event_draft: EventDraft
    state: KnowledgeState
    budget: ResearchBudget
    policy: DailySelectionPolicy


def build_scenario() -> FetchedSourceScenario:
    official_url = "https://official.example/model-x"
    repo_url = "https://repo.example/model-x"
    media_a_url = "https://media.example/a"
    media_b_url = "https://media.example/b"
    urls = (official_url, repo_url, media_a_url, media_b_url)
    artifacts = tuple(
        ArtifactRef(
            ArtifactKind.CANDIDATE, f"brave:{index}",
            metadata={"url": url, "title": f"Result {index}", "description": f"Brave snippet {index}", "provider_rank": index, "source_type": "brave_web_search_result", "external_source": True, "evidence_role": "discovery_only"},
        )
        for index, url in enumerate(urls, start=1)
    )
    observation = ProviderObservation(
        observation_id="obs:brave:fetched", action_id="action:brave:fetched",
        provider_id="provider.brave_search", surface_id="surface.brave_search.web",
        status=ObservationStatus.SUCCEEDED, artifacts=artifacts, raw_ref=None, result_count=4,
        cost={}, latency_ms=10.0, continuation={}, diagnostics=(), occurred_at=NOW,
        metadata={"query": "Model X release", "evidence_role": "discovery_only"},
    )
    html_by_url = {
        official_url: f'<link rel="canonical" href="{official_url}"><article>Official release.</article>',
        repo_url: f'<link rel="canonical" href="{repo_url}"><article>Repository release.</article>',
        media_a_url: f'<link rel="canonical" href="{media_a_url}"><link rel="original-source" href="{official_url}"><blockquote>Model X is available today from the official release.</blockquote>',
        media_b_url: f'<link rel="canonical" href="{media_b_url}"><link rel="syndication-source" href="{media_a_url}"><article>Syndicated report.</article>',
    }
    fetched_pages = tuple(
        FetchedPage(
            source_id=source_id(url), url=url, canonical_url=url, html=html_by_url[url],
            observed_at=NOW, published_at=f"2026-09-01T10:0{index}:00Z",
            content_hash=f"hash-{index}", title=f"Page {index}", author=None,
            content_ref=f"fixture:{index}", truncated=False,
        )
        for index, url in enumerate(urls)
    )
    source_nodes = tuple(
        SourceNode(
            source_id=page.source_id, url=page.url, canonical_url=page.canonical_url,
            published_at=page.published_at, observed_at=page.observed_at,
            owner_hint=None, content_hash=page.content_hash, metadata={},
        )
        for page in fetched_pages
    )
    evidence_items = tuple(
        evidence(eid, url)
        for eid, url in zip(("ev:official-blog", "ev:official-repo", "ev:media-a", "ev:media-b"), urls)
    )
    claim_draft = ClaimDraft(
        claim_id="claim:model-x-release-fetched", statement="Model X 已正式發布。",
        subject_id="model:model-x", predicate="released", object_value=True,
        state=ClaimState.CONFIRMED, claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence=evidence_items, independent_root_count=0, known_at=NOW,
        valid_time=ValidTime(start="2026-09-01T10:00:00Z"),
        metadata={"source_independence": "fetched_page_runtime"},
    )
    event_draft = EventDraft(
        event_id="evt:model-x-release-fetched", event_type=AIEventType.MODEL_RELEASE,
        entity_ids=("model:model-x", "org:company-y"), status=EventStatus.CONFIRMED,
        claim_ids=(claim_draft.claim_id,), evidence_ids=tuple(item.candidate_evidence_id for item in evidence_items),
        known_at=NOW, valid_time=claim_draft.valid_time,
        metadata={"discovery_observation_id": observation.observation_id},
    )
    state = KnowledgeState(
        state_id="Ksys:2026-09-01:ai-fetched-sources", mode=KnowledgeMode.SYSTEM_AS_KNOWN,
        as_of=NOW, policy_version="ai-daily-fetched-source-v1",
        claim_ids=(claim_draft.claim_id,), event_ids=(event_draft.event_id,), metadata={},
    )
    return FetchedSourceScenario(
        observation=observation, fetched_pages=fetched_pages, source_nodes=source_nodes,
        claim_draft=claim_draft, evidence_source_ids=tuple(source_id(url) for url in urls),
        event_draft=event_draft, state=state,
        budget=ResearchBudget(max_selected_events=1, max_watch_events=0),
        policy=DailySelectionPolicy(include_what_to_watch=False),
    )
