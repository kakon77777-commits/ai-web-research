import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.execution.runtime import ExecutionRuntime
from ai_web_research.execution.trusted import TrustedExecutionRejected, TrustedExecutionRuntime
from ai_web_research.experience.receipt import SearchReceiptRecorder, SearchReceiptStatus
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.crossref import CrossrefAdapter, crossref_policy_profile, register_crossref_provider
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.storage.trusted_sqlite import TrustedDataStore
from ai_web_research.experience.sqlite import SearchReceiptStore


class FakeResponse:
    status_code = 200
    headers = {
        "x-rate-limit-limit": "1",
        "x-rate-limit-interval": "1s",
        "x-concurrency-limit": "1",
    }

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": "ok",
            "message": {
                "items": [
                    {
                        "DOI": "10.5555/ausi",
                        "title": ["AUSI Example"],
                        "container-title": ["Example Journal"],
                        "publisher": "Example",
                        "type": "journal-article",
                        "URL": "https://doi.org/10.5555/ausi",
                        "published": {"date-parts": [[2026, 1, 1]]},
                    }
                ]
            },
        }


class FakeClient:
    async def get(self, url, *, params=None, headers=None):
        return FakeResponse()


def build(tmp_path, include_policy=True):
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    providers = ProviderRegistry()
    register_crossref_provider(providers, methods.snapshot())
    provider_snapshot = providers.snapshot()

    adapters = AdapterRegistry()
    adapters.register(CrossrefAdapter())
    execution = ExecutionRuntime(adapters, provider_snapshot)

    policies = SourcePolicyRegistry()
    if include_policy:
        policies.register(crossref_policy_profile())

    store = TrustedDataStore(tmp_path / "trusted.db")
    receipt_store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(receipt_store)
    trusted = TrustedExecutionRuntime(
        execution=execution,
        providers=provider_snapshot,
        policies=policies.snapshot(),
        evaluator=DeterministicPolicyEvaluator(),
        store=store,
        receipt_recorder=recorder,
    )
    return trusted, recorder, store, receipt_store


def action():
    return SearchAction(
        action_id="crossref-live-1",
        task_id="task-crossref",
        epoch_id="epoch-crossref",
        method_ref=VersionRef("method.lexical_search", "1.0.0"),
        provider_ref=VersionRef("provider.crossref", "1.0.0"),
        surface_id="surface.crossref.rest",
        binding_id="binding.lexical_search.crossref.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"query": "autonomous research", "top_k": 2},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def exec_context():
    return ExecutionContext(
        task_id="task-crossref",
        epoch_id="epoch-crossref",
        registry_snapshot_id="registry-crossref",
        services={
            "crossref_http_client": FakeClient(),
            "clock": "2026-08-31T12:00:01+00:00",
        },
        runtime_limits={},
    )


def policy_context():
    return PolicyContext(
        task_id="task-crossref",
        purpose="research",
        party_profile_id=None,
        risk_class=RiskClass.LOW,
        jurisdiction_context=(),
        requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
        timestamp="2026-08-31T12:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_crossref_trusted_execution_automatically_records_action_and_final_receipt(tmp_path):
    trusted, recorder, store, receipt_store = build(tmp_path)
    try:
        result = await trusted.execute(action(), exec_context(), policy_context())
        assert result.observation.result_count == 1
        assert len(result.materialized_assets) == 1
        assert result.materialized_assets[0].asset.artifact_ref.id == "crossref:doi:10.5555/ausi"

        action_receipts = receipt_store.list_search_action_receipts("epoch-crossref")
        assert len(action_receipts) == 1
        assert action_receipts[0].provider_ref.id == "provider.crossref"
        assert action_receipts[0].policy_decision.value == "allow_with_obligations"
        assert action_receipts[0].artifact_refs == ("crossref:doi:10.5555/ausi",)

        final = recorder.finalize(
            receipt_id="receipt-crossref",
            task_id="task-crossref",
            epoch_id="epoch-crossref",
            registry_snapshot_id="registry-crossref",
            planner_id="planner.rule",
            planner_version="0.1.0",
            stop_reason="FIRST_PROVIDER_SLICE_COMPLETE",
            status=SearchReceiptStatus.PARTIAL,
            created_at="2026-08-31T12:00:02+00:00",
            metadata={"provider": "crossref"},
        )
        assert final.actions == action_receipts
        assert receipt_store.get_search_receipt("receipt-crossref") == final
    finally:
        store.close()
        receipt_store.close()


@pytest.mark.asyncio
async def test_crossref_unknown_policy_is_receipted_but_never_calls_external_provider(tmp_path):
    trusted, _, store, receipt_store = build(tmp_path, include_policy=False)
    try:
        with pytest.raises(TrustedExecutionRejected):
            await trusted.execute(action(), exec_context(), policy_context())
        receipts = receipt_store.list_search_action_receipts("epoch-crossref")
        assert len(receipts) == 1
        assert receipts[0].policy_decision.value == "unknown"
        assert receipts[0].observation_id is None
        assert receipts[0].metadata["rejected_before_provider_execution"] is True
    finally:
        store.close()
        receipt_store.close()


class FailingClient:
    async def get(self, url, *, params=None, headers=None):
        raise RuntimeError("transport boom")


@pytest.mark.asyncio
async def test_provider_failure_is_receipted(tmp_path):
    trusted, _, store, receipt_store = build(tmp_path)
    failing_ctx = ExecutionContext(
        task_id="task-crossref",
        epoch_id="epoch-crossref",
        registry_snapshot_id="registry-crossref",
        services={
            "crossref_http_client": FailingClient(),
            "clock": "2026-08-31T12:00:01+00:00",
        },
        runtime_limits={},
    )
    try:
        with pytest.raises(Exception):
            await trusted.execute(action(), failing_ctx, policy_context())
        receipts = receipt_store.list_search_action_receipts("epoch-crossref")
        assert len(receipts) == 1
        assert receipts[0].observation_status is not None
        assert receipts[0].observation_status.value == "failed"
        assert "PROVIDER_EXECUTION_ERROR" in receipts[0].reason_codes
        assert receipts[0].metadata["exception_type"] in {
            "RuntimeError", "CrossrefAdapterError"
        }
    finally:
        store.close()
        receipt_store.close()
