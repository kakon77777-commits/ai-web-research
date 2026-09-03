from pathlib import Path

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    SearchAction,
    VersionRef,
)
from ai_web_research.execution.models import (
    AuthorizationResult,
    ObservationStatus,
    PolicyDecision,
    ProviderObservation,
)
from ai_web_research.experience.receipt import SearchReceiptRecorder
from ai_web_research.experience.sqlite import SearchReceiptStore
from ai_web_research.policy.models import PolicyEvaluation, UsageEnvelopeSeed
from ai_web_research.routing.models import (
    PolicyFreshness,
    ProviderAvailability,
    RoutingCandidateEvaluation,
    RoutingDecision,
)


def action():
    return SearchAction(
        action_id="a1",
        task_id="task1",
        epoch_id="epoch1",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.grok", "1.0.0"),
        surface_id="surface.grok.web_search",
        binding_id="binding.lexical_search.grok_web.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"query": "AI research"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner",
        created_at="2026-09-03T06:00:00+00:00",
    )


def evaluation(decision=PolicyDecision.ALLOW):
    return PolicyEvaluation(
        authorization=AuthorizationResult(
            decision=decision,
            policy_refs=("policy.grok.web_search@1.0.0",),
            reason_codes=("EXPLICIT_PERMISSION",) if decision in {PolicyDecision.ALLOW, PolicyDecision.ALLOW_WITH_OBLIGATIONS} else ("POLICY_BLOCK",),
        ),
        usage_seed=UsageEnvelopeSeed(),
        robots_ref=None,
    )


def observation():
    return ProviderObservation(
        observation_id="obs1",
        action_id="a1",
        provider_id="provider.grok",
        surface_id="surface.grok.web_search",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(ArtifactRef(ArtifactKind.CANDIDATE, "c1", metadata={"url": "https://example.org"}),),
        raw_ref=None,
        result_count=1,
        cost={},
        latency_ms=321.0,
        continuation={},
        diagnostics=(),
        occurred_at="2026-09-03T06:00:01+00:00",
        metadata={},
    )


def routing_decision():
    return RoutingDecision(
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        routing_policy_id="routing.default",
        provider_registry_snapshot_id="provider-snapshot",
        provider_state_snapshot_id="state-snapshot",
        selected_binding_id="binding.lexical_search.grok_web.v1",
        selected_provider_ref=VersionRef("provider.grok", "1.0.0"),
        selected_surface_id="surface.grok.web_search",
        candidates=(
            RoutingCandidateEvaluation(
                binding_id="binding.lexical_search.gemini_google_vertex.v1",
                provider_ref=VersionRef("provider.gemini_google_vertex", "1.0.0"),
                surface_id="surface.gemini.google_search_vertex",
                eligible=False,
                reason_codes=("QUOTA_EXHAUSTED",),
                availability=ProviderAvailability.AVAILABLE,
                credential_available=True,
                quota_remaining=0.0,
                estimated_cost=0.0,
                estimated_latency_ms=400.0,
                policy_freshness=PolicyFreshness.FRESH,
                model_available=True,
            ),
            RoutingCandidateEvaluation(
                binding_id="binding.lexical_search.grok_web.v1",
                provider_ref=VersionRef("provider.grok", "1.0.0"),
                surface_id="surface.grok.web_search",
                eligible=True,
                reason_codes=(),
                availability=ProviderAvailability.AVAILABLE,
                credential_available=True,
                quota_remaining=50.0,
                estimated_cost=0.02,
                estimated_latency_ms=600.0,
                policy_freshness=PolicyFreshness.FRESH,
                model_available=True,
            ),
        ),
        reason_codes=("SELECTED_BY_BINDING_PREFERENCE",),
    )


def assert_routing_metadata(receipt):
    routing = receipt.metadata["routing"]
    assert routing["selected_binding_id"] == "binding.lexical_search.grok_web.v1"
    assert routing["provider_state_snapshot_id"] == "state-snapshot"
    assert routing["candidates"][0]["reason_codes"] == ["QUOTA_EXHAUSTED"]
    rendered = repr(receipt)
    assert "credential-value-must-not-leak" not in rendered


def test_success_receipt_records_sanitized_routing_decision(tmp_path: Path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    try:
        recorder = SearchReceiptRecorder(store)
        receipt = recorder.record_success(
            action=action(),
            evaluation=evaluation(),
            observation=observation(),
            routing_decision=routing_decision(),
        )
        assert_routing_metadata(receipt)
        loaded = store.list_search_action_receipts("epoch1")[0]
        assert loaded.metadata["routing"] == receipt.metadata["routing"]
    finally:
        store.close()


def test_rejected_receipt_records_same_routing_decision(tmp_path: Path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    try:
        receipt = SearchReceiptRecorder(store).record_rejected(
            action=action(),
            evaluation=evaluation(PolicyDecision.DENY),
            occurred_at="2026-09-03T06:00:01+00:00",
            routing_decision=routing_decision(),
        )
        assert_routing_metadata(receipt)
        assert receipt.metadata["rejected_before_provider_execution"] is True
    finally:
        store.close()


def test_failed_receipt_records_same_routing_decision(tmp_path: Path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    try:
        receipt = SearchReceiptRecorder(store).record_failed(
            action=action(),
            evaluation=evaluation(),
            occurred_at="2026-09-03T06:00:01+00:00",
            exception=RuntimeError("provider failed"),
            routing_decision=routing_decision(),
        )
        assert_routing_metadata(receipt)
        assert receipt.metadata["provider_execution_failed"] is True
    finally:
        store.close()
