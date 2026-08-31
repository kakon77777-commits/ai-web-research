from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    SearchAction,
    VersionRef,
)
from ai_web_research.evidence.materialize import materialize_acquired_assets
from ai_web_research.execution.models import (
    AuthorizationResult,
    AuthorizedAction,
    ObservationStatus,
    PolicyDecision,
    ProviderObservation,
)
from ai_web_research.policy.models import AcquisitionAction, Obligation, UsageEnvelopeSeed


def make_action():
    return SearchAction(
        action_id="a1",
        task_id="t1",
        epoch_id="e1",
        method_ref=VersionRef("method.fetch_document", "1.0.0"),
        provider_ref=VersionRef("provider.crawler", "1.0.0"),
        surface_id="surface.crawler.browser",
        binding_id="binding.fetch_document.crawler.v1",
        action_kind=ActionKind.FETCH,
        inputs=(),
        parameters={"url": "https://example.com/a"},
        guards=(),
        expected_effects=("document_fetched",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def make_authorized():
    seed = UsageEnvelopeSeed(
        permissions=(AcquisitionAction.FETCH, AcquisitionAction.INTERNAL_USE),
        obligations=(
            Obligation(
                obligation_id="attribute",
                kind="attribution",
                parameters={"text": "Example"},
                persists_downstream=True,
                policy_refs=("src1",),
            ),
        ),
        policy_refs=("policy.example@1.0.0",),
    )
    return AuthorizedAction(
        action=make_action(),
        authorization=AuthorizationResult(
            PolicyDecision.ALLOW_WITH_OBLIGATIONS,
            obligations=("attribute",),
            policy_refs=("policy.example@1.0.0",),
        ),
        credential_profile_id=None,
        usage_seed=seed,
    )


def test_authorized_action_can_carry_usage_seed_without_secret_fields():
    authorized = make_authorized()
    assert authorized.usage_seed is not None
    assert AcquisitionAction.FETCH in authorized.usage_seed.permissions
    assert not hasattr(authorized, "api_key")


def test_successful_observation_materializes_asset_and_usage_envelope():
    authorized = make_authorized()
    obs = ProviderObservation(
        observation_id="obs1",
        action_id="a1",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(
                ArtifactKind.DOCUMENT,
                "doc1",
                metadata={
                    "url": "https://example.com/a",
                    "media_type": "text/html",
                    "content_hash": "abc",
                },
            ),
        ),
        raw_ref="storage/raw/a.html",
        result_count=1,
        cost={},
        latency_ms=3.0,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T12:00:01+00:00",
        metadata={},
    )
    materialized = materialize_acquired_assets(authorized, obs)
    assert len(materialized) == 1
    item = materialized[0]
    assert item.asset.asset_id == "obs1:asset:1"
    assert item.asset.artifact_ref.id == "doc1"
    assert item.asset.content_hash == "abc"
    assert item.asset.usage_envelope_id == item.usage_envelope.envelope_id
    assert AcquisitionAction.INTERNAL_USE in item.usage_envelope.permissions
    assert item.usage_envelope.obligations[0].obligation_id == "attribute"


def test_one_observation_can_materialize_multiple_assets():
    authorized = make_authorized()
    obs = ProviderObservation(
        observation_id="obs2",
        action_id="a1",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(ArtifactKind.DOCUMENT, "doc1", metadata={"url": "https://example.com/1"}),
            ArtifactRef(ArtifactKind.DOCUMENT, "doc2", metadata={"url": "https://example.com/2"}),
        ),
        raw_ref=None,
        result_count=2,
        cost={},
        latency_ms=None,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T12:00:02+00:00",
        metadata={},
    )
    materialized = materialize_acquired_assets(authorized, obs)
    assert [m.asset.asset_id for m in materialized] == ["obs2:asset:1", "obs2:asset:2"]


def test_failed_observation_materializes_no_successful_assets():
    authorized = make_authorized()
    obs = ProviderObservation(
        observation_id="obs3",
        action_id="a1",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        status=ObservationStatus.FAILED,
        artifacts=(ArtifactRef(ArtifactKind.DOCUMENT, "doc1"),),
        raw_ref=None,
        result_count=0,
        cost={},
        latency_ms=None,
        continuation={},
        diagnostics=("failed",),
        occurred_at="2026-08-31T12:00:03+00:00",
        metadata={},
    )
    assert materialize_acquired_assets(authorized, obs) == ()
