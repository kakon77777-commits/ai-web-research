from dataclasses import dataclass

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.domains.ai_industry.daily import DailySelectionPolicy
from ai_web_research.domains.ai_industry.models import AIEventType, ClaimDraft, EventDraft
from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.execution.models import ObservationStatus, ProviderObservation
from ai_web_research.knowledge.models import ClaimOrigin, ClaimState, EventStatus, KnowledgeMode, KnowledgeState, ValidTime
from ai_web_research.resource_control.models import ResearchBudget
from ai_web_research.source_graph.models import RelationInferenceType, SourceNode, SourceRelation, SourceRelationType
from ai_web_research.source_graph.trace import SourceTraceSignals

NOW = '2026-08-31T16:00:00Z'


def source_id(url: str) -> str:
    return f'source:{url.rstrip("/")}'


def evidence(eid: str, source_url: str) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_evidence_id=eid,
        acquired_asset_id=f'asset:{eid}',
        field_name='key_claim',
        extracted_value='Model X was released.',
        source_identity_ref=source_id(source_url),
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=(f'anchor:{eid}',),
        extraction_method='fixture_fetched_page',
        extractor_version='fixture-v1',
        model_ref=None,
        source_type='fetched_anchored_source',
        usage_envelope_id='usage:fixture',
        extractor_confidence=1.0,
        semantic_support_verified=False,
        validation_notes=(),
        created_at=NOW,
    )


@dataclass(frozen=True)
class LiveDiscoveryScenario:
    observation: ProviderObservation
    source_nodes: tuple[SourceNode, ...]
    base_relations: tuple[SourceRelation, ...]
    trace_signals_by_source: dict[str, SourceTraceSignals]
    claim_draft: ClaimDraft
    evidence_source_ids: tuple[str, ...]
    event_draft: EventDraft
    state: KnowledgeState
    budget: ResearchBudget
    policy: DailySelectionPolicy


def build_scenario() -> LiveDiscoveryScenario:
    official_url = 'https://official.example/model-x'
    repo_url = 'https://repo.example/model-x'
    media_a_url = 'https://media.example/a'
    media_b_url = 'https://media.example/b'

    urls = (official_url, repo_url, media_a_url, media_b_url)
    titles = ('Official Model X', 'Model X Repository', 'Media A', 'Media B')
    descriptions = (
        'Brave snippet official release',
        'Brave snippet repository',
        'Brave snippet media a',
        'Brave snippet media b',
    )
    artifacts = tuple(
        ArtifactRef(
            ArtifactKind.CANDIDATE,
            f'brave:{index}',
            metadata={
                'url': url,
                'title': title,
                'description': description,
                'provider_rank': index,
                'source_type': 'brave_web_search_result',
                'external_source': True,
                'evidence_role': 'discovery_only',
            },
        )
        for index, (url, title, description) in enumerate(zip(urls, titles, descriptions), start=1)
    )
    observation = ProviderObservation(
        observation_id='obs:brave:model-x',
        action_id='action:brave:model-x',
        provider_id='provider.brave_search',
        surface_id='surface.brave_search.web',
        status=ObservationStatus.SUCCEEDED,
        artifacts=artifacts,
        raw_ref=None,
        result_count=4,
        cost={},
        latency_ms=12.0,
        continuation={},
        diagnostics=(),
        occurred_at=NOW,
        metadata={'query': 'Model X release', 'evidence_role': 'discovery_only'},
    )

    source_nodes = tuple(
        SourceNode(
            source_id=source_id(url),
            url=url,
            canonical_url=url,
            published_at=f'2026-08-31T10:0{index}:00Z',
            observed_at=NOW,
            owner_hint=None,
            content_hash=f'hash-{index}',
            metadata={},
        )
        for index, url in enumerate(urls)
    )
    media_a_id = source_id(media_a_url)
    media_b_id = source_id(media_b_url)
    official_id = source_id(official_url)
    repo_id = source_id(repo_url)

    base_relations = (
        SourceRelation(
            relation_id='rel:media-b-syndicated-media-a',
            from_source_id=media_b_id,
            to_source_id=media_a_id,
            relation_type=SourceRelationType.SYNDICATED_FROM,
            confidence=1.0,
            inference_type=RelationInferenceType.EXPLICIT,
            signals=('fixture_syndication_marker',),
        ),
    )
    trace_signals_by_source = {
        media_a_id: SourceTraceSignals(
            attributed_source_urls=(official_url,),
            attribution_entities=('Company Y',),
            quoted_phrases=('Model X is available today',),
            claim_keywords=('Model X', 'release'),
        )
    }

    blog_ev = evidence('ev:official-blog', official_url)
    repo_ev = evidence('ev:official-repo', repo_url)
    media_a_ev = evidence('ev:media-a', media_a_url)
    media_b_ev = evidence('ev:media-b', media_b_url)
    claim_draft = ClaimDraft(
        claim_id='claim:model-x-release-live',
        statement='Model X 已正式發布。',
        subject_id='model:model-x',
        predicate='released',
        object_value=True,
        state=ClaimState.CONFIRMED,
        claim_origin=ClaimOrigin.SOURCE_ASSERTION,
        evidence=(blog_ev, repo_ev, media_a_ev, media_b_ev),
        independent_root_count=0,
        known_at=NOW,
        valid_time=ValidTime(start='2026-08-31T10:00:00Z'),
        metadata={'source_independence': 'runtime_resolved'},
    )
    evidence_source_ids = (official_id, repo_id, media_a_id, media_b_id)
    event_draft = EventDraft(
        event_id='evt:model-x-release-live',
        event_type=AIEventType.MODEL_RELEASE,
        entity_ids=('model:model-x', 'org:company-y'),
        status=EventStatus.CONFIRMED,
        claim_ids=(claim_draft.claim_id,),
        evidence_ids=tuple(item.candidate_evidence_id for item in claim_draft.evidence),
        known_at=NOW,
        valid_time=claim_draft.valid_time,
        metadata={'discovery_observation_id': observation.observation_id},
    )
    state = KnowledgeState(
        state_id='Ksys:2026-08-31:ai-live-discovery',
        mode=KnowledgeMode.SYSTEM_AS_KNOWN,
        as_of=NOW,
        policy_version='ai-daily-live-discovery-v1',
        claim_ids=(claim_draft.claim_id,),
        event_ids=(event_draft.event_id,),
        metadata={},
    )
    return LiveDiscoveryScenario(
        observation=observation,
        source_nodes=source_nodes,
        base_relations=base_relations,
        trace_signals_by_source=trace_signals_by_source,
        claim_draft=claim_draft,
        evidence_source_ids=evidence_source_ids,
        event_draft=event_draft,
        state=state,
        budget=ResearchBudget(max_selected_events=1, max_watch_events=0),
        policy=DailySelectionPolicy(include_what_to_watch=False),
    )
