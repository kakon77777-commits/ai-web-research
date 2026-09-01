from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.execution.models import (
    AuthorizationResult,
    AuthorizedAction,
    ErrorCategory,
    ExecutionContext,
    ObservationStatus,
    PolicyDecision,
    ProviderObservation,
    RuntimeErrorRecord,
)


def make_action() -> SearchAction:
    return SearchAction(
        action_id="epoch-1:action:1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.identity_search", "1.0.0"),
        provider_ref=VersionRef("provider.local_corpus", "1.0.0"),
        surface_id="surface.local.sqlite",
        binding_id="binding.identity_search.local_corpus.v1",
        action_kind=ActionKind.RESOLVE_IDENTITY,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"query": "alpha"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T09:00:00+00:00",
    )


def test_only_allow_decisions_are_executable():
    assert AuthorizationResult(PolicyDecision.ALLOW).is_executable
    assert AuthorizationResult(PolicyDecision.ALLOW_WITH_OBLIGATIONS).is_executable
    assert not AuthorizationResult(PolicyDecision.DENY).is_executable
    assert not AuthorizationResult(PolicyDecision.UNKNOWN).is_executable
    assert not AuthorizationResult(PolicyDecision.REVIEW).is_executable


def test_authorized_action_keeps_only_credential_profile_reference():
    wrapped = AuthorizedAction(
        action=make_action(),
        authorization=AuthorizationResult(PolicyDecision.ALLOW),
        credential_profile_id="credential.vertex.default",
    )
    assert wrapped.credential_profile_id == "credential.vertex.default"
    assert not hasattr(wrapped, "api_key")
    assert not hasattr(wrapped, "access_token")


def test_provider_observation_preserves_execution_identity():
    obs = ProviderObservation(
        observation_id="obs-1",
        action_id="epoch-1:action:1",
        provider_id="provider.local_corpus",
        surface_id="surface.local.sqlite",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(ArtifactRef(ArtifactKind.CANDIDATE, "doc-1"),),
        raw_ref=None,
        result_count=1,
        cost={},
        latency_ms=1.5,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T09:00:01+00:00",
        metadata={},
    )
    assert obs.action_id == "epoch-1:action:1"
    assert obs.provider_id == "provider.local_corpus"
    assert obs.surface_id == "surface.local.sqlite"
    assert obs.artifacts[0].kind is ArtifactKind.CANDIDATE


def test_execution_context_can_carry_runtime_services_without_serializing_secrets():
    marker = object()
    ctx = ExecutionContext(
        task_id="task-1",
        epoch_id="epoch-1",
        registry_snapshot_id="snapshot-1",
        services={"page_store": marker},
        runtime_limits={"max_results": 10},
    )
    assert ctx.services["page_store"] is marker
    assert ctx.runtime_limits["max_results"] == 10


def test_runtime_error_record_is_typed():
    err = RuntimeErrorRecord(
        code="PROVIDER_TIMEOUT",
        category=ErrorCategory.TIMEOUT,
        message="timed out",
        recoverable=True,
        action_id="a1",
        provider_id="provider.x",
        retry_after_seconds=1.0,
        metadata={},
    )
    assert err.category is ErrorCategory.TIMEOUT
    assert err.recoverable is True
