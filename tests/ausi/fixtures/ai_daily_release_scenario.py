from dataclasses import dataclass

from ai_web_research.domains.ai_industry.canonicalize import canonicalize_event, promote_claim
from ai_web_research.domains.ai_industry.daily import DailyEventInput
from ai_web_research.domains.ai_industry.models import AIEventType, ClaimDraft, EventDraft
from ai_web_research.evidence.models import CandidateEvidence
from ai_web_research.knowledge.models import (
    CanonicalClaim,
    CanonicalEvent,
    ClaimOrigin,
    ClaimState,
    EventStatus,
    KnowledgeMode,
    KnowledgeState,
    ValidTime,
)

NOW = "2026-08-31T12:00:00Z"


@dataclass(frozen=True)
class AIDailyReleaseScenario:
    claims: tuple[CanonicalClaim, ...]
    events: tuple[CanonicalEvent, ...]
    state: KnowledgeState
    candidates: tuple[DailyEventInput, ...]
    evidence_locators: dict[str, str]
    release_claim_id: str
    release_event_id: str
    rumor_event_id: str
    api_event_id: str


def _evidence(evidence_id: str, source_identity_ref: str, source_type: str) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_evidence_id=evidence_id,
        acquired_asset_id=f"asset:{evidence_id}",
        field_name="key_claim",
        extracted_value="fixture",
        source_identity_ref=source_identity_ref,
        work_identity_ref=None,
        version_identity_ref=None,
        manifestation_identity_ref=None,
        anchor_refs=(f"anchor:{evidence_id}",),
        extraction_method="fixture",
        extractor_version="fixture-v1",
        model_ref=None,
        source_type=source_type,
        usage_envelope_id="usage:fixture",
        extractor_confidence=1.0,
        semantic_support_verified=False,
        validation_notes=(),
        created_at=NOW,
    )


def build_scenario() -> AIDailyReleaseScenario:
    blog = _evidence("ev:official-blog", "source:official-blog", "primary_official")
    repo = _evidence("ev:official-repo", "source:official-repo", "primary_code")
    media1 = _evidence("ev:media-1", "source:media-1", "secondary_syndicated")
    media2 = _evidence("ev:media-2", "source:media-2", "secondary_syndicated")
    paper_ev = _evidence("ev:paper", "source:paper", "primary_paper")
    rumor_ev = _evidence("ev:reporter", "source:reporter", "social_primary")
    api_ev = _evidence("ev:api-announcement", "source:official-api-doc", "primary_official")

    root_family_by_evidence = {
        blog.candidate_evidence_id: "root:official-blog",
        repo.candidate_evidence_id: "root:official-repo",
        media1.candidate_evidence_id: "root:official-blog",
        media2.candidate_evidence_id: "root:official-blog",
    }
    release_root_count = len(set(root_family_by_evidence.values()))

    release = promote_claim(
        ClaimDraft(
            claim_id="claim:model-x-release-license",
            statement="Model X 已正式發布；目前公開資料標示授權為 License L1。",
            subject_id="model:model-x",
            predicate="released_with_license",
            object_value={"released": True, "license": "L1"},
            state=ClaimState.CONFIRMED,
            claim_origin=ClaimOrigin.SOURCE_ASSERTION,
            evidence=(blog, repo, media1, media2),
            independent_root_count=release_root_count,
            known_at=NOW,
            valid_time=ValidTime(start="2026-08-31T09:00:00Z"),
            metadata={"root_family_by_evidence": root_family_by_evidence},
        )
    )
    paper = promote_claim(
        ClaimDraft(
            claim_id="claim:paper-release",
            statement="研究團隊公開了 Model X 的技術報告。",
            subject_id="paper:model-x-report",
            predicate="released",
            object_value=True,
            state=ClaimState.WELL_SUPPORTED,
            claim_origin=ClaimOrigin.SOURCE_ASSERTION,
            evidence=(paper_ev,),
            independent_root_count=1,
            known_at=NOW,
            valid_time=ValidTime(start="2026-08-31T10:00:00Z"),
            metadata={},
        )
    )
    rumor = promote_claim(
        ClaimDraft(
            claim_id="claim:model-x-next-rumor",
            statement="有消息稱 Model X 可能很快推出下一個版本。",
            subject_id="model:model-x-next",
            predicate="possible_release",
            object_value=True,
            state=ClaimState.UNVERIFIED,
            claim_origin=ClaimOrigin.SOURCE_ASSERTION,
            evidence=(rumor_ev,),
            independent_root_count=1,
            known_at=NOW,
            valid_time=None,
            metadata={},
        )
    )
    api = promote_claim(
        ClaimDraft(
            claim_id="claim:model-x-api-availability",
            statement="官方已宣布 API，但尚未確認所有用戶均可實際使用。",
            subject_id="api:model-x",
            predicate="availability",
            object_value="announced_not_operationally_confirmed",
            state=ClaimState.UNVERIFIED,
            claim_origin=ClaimOrigin.SOURCE_ASSERTION,
            evidence=(api_ev,),
            independent_root_count=1,
            known_at=NOW,
            valid_time=None,
            metadata={},
        )
    )

    release_event = canonicalize_event(
        EventDraft(
            event_id="evt:model-x-release",
            event_type=AIEventType.MODEL_RELEASE,
            entity_ids=("model:model-x", "org:company-y"),
            status=EventStatus.CONFIRMED,
            claim_ids=(release.claim_id,),
            evidence_ids=release.evidence_ids,
            known_at=NOW,
            valid_time=release.valid_time,
            metadata={"same_event_observations": 4},
        )
    )
    paper_event = canonicalize_event(
        EventDraft(
            event_id="evt:model-x-paper",
            event_type=AIEventType.PAPER_RELEASE,
            entity_ids=("paper:model-x-report", "model:model-x"),
            status=EventStatus.CONFIRMED,
            claim_ids=(paper.claim_id,),
            evidence_ids=paper.evidence_ids,
            known_at=NOW,
            valid_time=paper.valid_time,
            metadata={},
        )
    )
    rumor_event = canonicalize_event(
        EventDraft(
            event_id="evt:model-x-next-rumor",
            event_type=AIEventType.RUMOR_DETECTED,
            entity_ids=("model:model-x-next",),
            status=EventStatus.CANDIDATE,
            claim_ids=(rumor.claim_id,),
            evidence_ids=rumor.evidence_ids,
            known_at=NOW,
            valid_time=None,
            metadata={},
        )
    )
    api_event = canonicalize_event(
        EventDraft(
            event_id="evt:model-x-api-announced",
            event_type=AIEventType.API_LAUNCH,
            entity_ids=("api:model-x",),
            status=EventStatus.CANDIDATE,
            claim_ids=(api.claim_id,),
            evidence_ids=api.evidence_ids,
            known_at=NOW,
            valid_time=None,
            metadata={"operationally_confirmed": False},
        )
    )

    claims = (release, paper, rumor, api)
    events = (release_event, paper_event, rumor_event, api_event)
    state = KnowledgeState(
        state_id="Ksys:2026-08-31:ai-daily",
        mode=KnowledgeMode.SYSTEM_AS_KNOWN,
        as_of=NOW,
        policy_version="ai-daily-v1",
        claim_ids=tuple(claim.claim_id for claim in claims),
        event_ids=tuple(event.event_id for event in events),
        metadata={"fixture": "model-x-release"},
    )
    candidates = (
        DailyEventInput(release_event, (release,), 0.98, 1.0, 0.95, 0.99),
        DailyEventInput(paper_event, (paper,), 0.70, 0.85, 0.65, 0.90),
        DailyEventInput(rumor_event, (rumor,), 0.85, 1.0, 0.75, 0.35),
        DailyEventInput(api_event, (api,), 0.90, 1.0, 0.90, 0.45),
    )
    evidence_locators = {
        "ev:official-blog": "fixture://official-blog#release",
        "ev:official-repo": "fixture://repo#license",
        "ev:media-1": "fixture://media-1#syndicated",
        "ev:media-2": "fixture://media-2#syndicated",
        "ev:paper": "fixture://paper#title",
        "ev:reporter": "fixture://reporter#post",
        "ev:api-announcement": "fixture://api-doc#announcement",
    }
    return AIDailyReleaseScenario(
        claims=claims,
        events=events,
        state=state,
        candidates=candidates,
        evidence_locators=evidence_locators,
        release_claim_id=release.claim_id,
        release_event_id=release_event.event_id,
        rumor_event_id=rumor_event.event_id,
        api_event_id=api_event.event_id,
    )
