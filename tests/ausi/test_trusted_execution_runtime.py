import pytest

from ai_web_research.evidence.store import EvidenceClosureStore
from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    RiskClass,
    SearchAction,
    VersionRef,
)
from ai_web_research.execution.models import ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.execution.runtime import ExecutionRuntime
from ai_web_research.execution.trusted import TrustedExecutionRejected, TrustedExecutionRuntime
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import (
    AcquisitionAction,
    PolicyContext,
    PolicyRule,
    PolicyRuleEffect,
    PolicySourceRef,
    SourcePolicyProfile,
)
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import (
    MethodBinding,
    ProviderKind,
    ProviderSpec,
    ProviderSurface,
    SurfaceKind,
)
from ai_web_research.storage.trusted_sqlite import TrustedDataStore


class FakeExtractionAdapter:
    adapter_id = "fake.extract"
    adapter_version = "1.0.0"

    def __init__(self):
        self.calls = 0

    async def execute(self, authorized, context):
        self.calls += 1
        return ProviderObservation(
            observation_id="obs-trusted-1",
            action_id=authorized.action.action_id,
            provider_id=authorized.action.provider_ref.id,
            surface_id=authorized.action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(
                ArtifactRef(
                    ArtifactKind.EVIDENCE_CANDIDATE,
                    "extract-result-1",
                    metadata={
                        "document_id": "doc1",
                        "url": "https://example.com/doc1",
                        "extractor_version": "extractor/1",
                        "provider": "fake",
                        "model": "fake-model",
                        "fields": {
                            "answer": {
                                "value": "42",
                                "source_quote": "the answer is 42",
                                "confidence": 0.91,
                                "quote_verified": True,
                            }
                        },
                        "validation_errors": [],
                        "source_type": "web_crawled_extraction",
                        "verification_scope": "anchor_only",
                        "semantic_support_verified": False,
                    },
                ),
            ),
            raw_ref="raw/doc1.html",
            result_count=1,
            cost={},
            latency_ms=1.0,
            continuation={},
            diagnostics=(),
            occurred_at="2026-08-31T12:00:01+00:00",
            metadata={},
        )


def setup_runtime(tmp_path, *, include_permission=True, prohibit=False):
    provider = ProviderSpec(
        provider_id="provider.fake",
        version="1.0.0",
        kind=ProviderKind.CUSTOM,
        display_name="Fake",
        domains=(),
        languages=(),
        jurisdictions=(),
        surfaces=(
            ProviderSurface(
                surface_id="surface.fake.api",
                kind=SurfaceKind.PUBLIC_API,
                endpoint_ref=None,
                capabilities=frozenset({"capability.extract_structured"}),
                auth_profile=None,
                policy_profile_refs=("policy.fake@1.0.0",),
                static_limits={},
                metadata={},
            ),
        ),
        metadata={},
    )
    binding = MethodBinding(
        binding_id="binding.fake.extract.v1",
        method_ref=VersionRef("method.extract_candidate_evidence", "1.0.0"),
        provider_ref=VersionRef("provider.fake", "1.0.0"),
        surface_id="surface.fake.api",
        adapter_id="fake.extract",
        adapter_version="1.0.0",
        enabled=True,
        parameter_mapping={},
        metadata={},
    )
    providers = ProviderRegistrySnapshot("providers-snapshot", (provider,), (binding,))
    adapter = FakeExtractionAdapter()
    adapters = AdapterRegistry()
    adapters.register(adapter)
    execution = ExecutionRuntime(adapters, providers)

    policy_registry = SourcePolicyRegistry()
    if include_permission:
        effect = PolicyRuleEffect.PROHIBITION if prohibit else PolicyRuleEffect.PERMISSION
        source = PolicySourceRef(
            source_id="policy-source",
            uri="https://example.com/terms",
            title="Terms",
            retrieved_at="2026-08-31T00:00:00+00:00",
            effective_at=None,
            expires_at=None,
            content_hash="hash",
            anchor={},
            authority="provider",
            interpretation_status="human_verified",
        )
        policy_registry.register(
            SourcePolicyProfile(
                policy_id="policy.fake",
                version="1.0.0",
                provider_id="provider.fake",
                surface_id="surface.fake.api",
                asset_scope="*",
                rules=(
                    PolicyRule(
                        rule_id="rule",
                        action=AcquisitionAction.AUTOMATED_QUERY,
                        effect=effect,
                        value=True,
                        asset_scope="*",
                        party_scope=None,
                        purpose_scope=("research",),
                        constraints={},
                        source_refs=("policy-source",),
                        priority_hint=1,
                    ),
                ),
                policy_sources=(source,),
                auth_requirements={},
                rate_limits={},
                retention_rules={},
                attribution_rules={},
                redistribution_rules={},
                privacy_flags=(),
                observed_at="2026-08-31T00:00:00+00:00",
                effective_at=None,
                expires_at=None,
                next_review_at=None,
                policy_hash="policyhash",
                review_status="verified",
                metadata={},
            )
        )
    store = TrustedDataStore(tmp_path / "trusted.db")
    trusted = TrustedExecutionRuntime(
        execution=execution,
        providers=providers,
        policies=policy_registry.snapshot(),
        evaluator=DeterministicPolicyEvaluator(),
        store=store,
    )
    return trusted, adapter, store


def make_action():
    return SearchAction(
        action_id="trusted-action-1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.extract_candidate_evidence", "1.0.0"),
        provider_ref=VersionRef("provider.fake", "1.0.0"),
        surface_id="surface.fake.api",
        binding_id="binding.fake.extract.v1",
        action_kind=ActionKind.EXTRACT,
        inputs=(ArtifactRef(ArtifactKind.DOCUMENT, "doc1"),),
        parameters={"schema": {"type": "object"}},
        guards=(),
        expected_effects=("candidate_evidence_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def make_context():
    return ExecutionContext(
        task_id="task-1",
        epoch_id="epoch-1",
        registry_snapshot_id="providers-snapshot",
        services={},
        runtime_limits={},
    )


def policy_context():
    return PolicyContext(
        task_id="task-1",
        purpose="research",
        party_profile_id=None,
        risk_class=RiskClass.LOW,
        jurisdiction_context=(),
        requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
        timestamp="2026-08-31T12:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_allow_path_closes_policy_execution_asset_candidate_ledger_gap_loop(tmp_path):
    trusted, adapter, store = setup_runtime(tmp_path)
    try:
        result = await trusted.execute(make_action(), make_context(), policy_context())
        assert adapter.calls == 1
        assert result.observation.observation_id == "obs-trusted-1"
        assert len(result.materialized_assets) == 1
        assert len(result.candidate_bundles) == 1
        bundle = result.candidate_bundles[0]
        assert bundle.candidates[0].semantic_support_verified is False
        assert bundle.verifications[0].dimension.value == "anchor"
        assert bundle.verifications[0].decision.value == "pass"
        persisted_verification = EvidenceClosureStore(store).get_verification_result(
            bundle.verifications[0].verification_id
        )
        assert persisted_verification == bundle.verifications[0]
        assert result.gap_projections[0].gap_types[0].value == "missing_identity"

        events = store.list_ledger_events()
        event_types = [event.event_type for event in events]
        assert "ASSET_ACQUIRED" in event_types
        assert "EVIDENCE_CANDIDATE_CREATED" in event_types
        assert "ANCHOR_VERIFIED" in event_types
        assert "GAP_PROJECTED" in event_types
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("include_permission,prohibit", [(False, False), (True, True)])
async def test_unknown_or_deny_never_executes_adapter(tmp_path, include_permission, prohibit):
    trusted, adapter, store = setup_runtime(
        tmp_path, include_permission=include_permission, prohibit=prohibit
    )
    try:
        with pytest.raises(TrustedExecutionRejected):
            await trusted.execute(make_action(), make_context(), policy_context())
        assert adapter.calls == 0
        assert store.list_ledger_events() == ()
    finally:
        store.close()
