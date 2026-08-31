from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    SearchAction,
    VersionRef,
)
from ai_web_research.execution.models import ObservationStatus, PolicyDecision, ProviderObservation
from ai_web_research.experience.receipt import (
    SearchReceiptRecorder,
    SearchReceiptStatus,
)
from ai_web_research.gaps.projection import EvidenceGapType, GapProjection
from ai_web_research.policy.models import PolicyEvaluation, UsageEnvelopeSeed
from ai_web_research.execution.models import AuthorizationResult
from ai_web_research.experience.sqlite import SearchReceiptStore


def make_action(action_id="a1"):
    return SearchAction(
        action_id=action_id,
        task_id="task1",
        epoch_id="epoch1",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.crossref", "1.0.0"),
        surface_id="surface.crossref.rest",
        binding_id="binding.lexical_search.crossref.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"query": "AI agents"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def allow_eval():
    return PolicyEvaluation(
        authorization=AuthorizationResult(
            PolicyDecision.ALLOW,
            policy_refs=("policy.crossref.rest.metadata@1.0.0",),
            reason_codes=("EXPLICIT_PERMISSION",),
        ),
        usage_seed=UsageEnvelopeSeed(),
        robots_ref=None,
    )


def deny_eval():
    return PolicyEvaluation(
        authorization=AuthorizationResult(
            PolicyDecision.DENY,
            policy_refs=("policy.x@1.0.0",),
            reason_codes=("POLICY_PROHIBITION:deny",),
        ),
        usage_seed=UsageEnvelopeSeed(),
        robots_ref=None,
    )


def make_observation():
    return ProviderObservation(
        observation_id="obs1",
        action_id="a1",
        provider_id="provider.crossref",
        surface_id="surface.crossref.rest",
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(
                ArtifactKind.CANDIDATE,
                "crossref:doi:10.1/x",
                metadata={"doi": "10.1/x"},
            ),
        ),
        raw_ref=None,
        result_count=1,
        cost={"requests": 1},
        latency_ms=42.0,
        continuation={},
        diagnostics=(),
        occurred_at="2026-08-31T12:00:01+00:00",
        metadata={},
    )


def make_gap():
    return GapProjection(
        gap_projection_id="gap1",
        claim_id=None,
        evidence_refs=("candidate1",),
        gap_types=(EvidenceGapType.MISSING_IDENTITY,),
        mandatory=True,
        severity=1.0,
        reason_codes=("SOURCE_UNRESOLVED",),
        created_at="2026-08-31T12:00:02+00:00",
    )


def test_success_action_receipt_persists_observable_execution_only(tmp_path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(store)
    try:
        receipt = recorder.record_success(
            action=make_action(),
            evaluation=allow_eval(),
            observation=make_observation(),
            gap_projections=(make_gap(),),
        )
        assert receipt.action_id == "a1"
        assert receipt.method_ref.id == "method.lexical_search"
        assert receipt.provider_ref.id == "provider.crossref"
        assert receipt.policy_decision is PolicyDecision.ALLOW
        assert receipt.result_count == 1
        assert receipt.artifact_refs == ("crossref:doi:10.1/x",)
        assert receipt.gap_refs == ("gap1",)
        assert not hasattr(receipt, "chain_of_thought")
        assert not hasattr(receipt, "reasoning")

        loaded = store.list_search_action_receipts("epoch1")
        assert loaded == (receipt,)
    finally:
        store.close()


def test_policy_rejection_is_recorded_even_without_provider_observation(tmp_path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(store)
    try:
        receipt = recorder.record_rejected(
            action=make_action("blocked-a"),
            evaluation=deny_eval(),
            occurred_at="2026-08-31T12:00:00+00:00",
        )
        assert receipt.policy_decision is PolicyDecision.DENY
        assert receipt.observation_id is None
        assert receipt.result_count is None
        assert "POLICY_PROHIBITION:deny" in receipt.reason_codes
        assert store.list_search_action_receipts("epoch1") == (receipt,)
    finally:
        store.close()


def test_finalize_search_receipt_aggregates_action_history_and_persists(tmp_path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(store)
    try:
        recorder.record_success(
            action=make_action(),
            evaluation=allow_eval(),
            observation=make_observation(),
            gap_projections=(make_gap(),),
        )
        final = recorder.finalize(
            receipt_id="receipt1",
            task_id="task1",
            epoch_id="epoch1",
            registry_snapshot_id="registry1",
            planner_id="planner.rule",
            planner_version="0.1.0",
            stop_reason="PARTIAL",
            status=SearchReceiptStatus.PARTIAL,
            created_at="2026-08-31T12:00:03+00:00",
            metadata={"declared_scope": "crossref"},
        )
        assert len(final.actions) == 1
        assert final.actions[0].action_id == "a1"
        assert final.status is SearchReceiptStatus.PARTIAL
        loaded = store.get_search_receipt("receipt1")
        assert loaded == final
        assert loaded.registry_snapshot_id == "registry1"
    finally:
        store.close()


def test_same_action_receipt_id_cannot_silently_change(tmp_path):
    store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(store)
    try:
        first = recorder.record_rejected(
            action=make_action("blocked-a"),
            evaluation=deny_eval(),
            occurred_at="2026-08-31T12:00:00+00:00",
        )
        # Exact replay is idempotent.
        store.save_search_action_receipt(first)
        changed = first.__class__(
            **{**first.__dict__, "reason_codes": ("DIFFERENT",)}
        )
        try:
            store.save_search_action_receipt(changed)
        except Exception:
            pass
        else:
            raise AssertionError("same receipt id must not silently mutate")
    finally:
        store.close()
