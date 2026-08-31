from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import PolicyDecision
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import (
    AcquisitionAction,
    PolicyContext,
    PolicyRule,
    PolicyRuleEffect,
    PolicySourceRef,
    SourcePolicyProfile,
)
from ai_web_research.providers.spec import ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind


def _action():
    return SearchAction(
        action_id="a1", task_id="t1", epoch_id="e1",
        method_ref=VersionRef("method.crawl_discovery", "1.0.0"),
        provider_ref=VersionRef("provider.crawler", "1.0.0"),
        surface_id="surface.crawler.browser",
        binding_id="binding.crawl_discovery.crawler.v1",
        action_kind=ActionKind.CRAWL,
        inputs=(ArtifactRef(ArtifactKind.SEED, "seed1"),),
        parameters={}, guards=(), expected_effects=(), created_by="test",
        created_at="2026-08-31T12:00:00+00:00",
    )


def _provider():
    surface = ProviderSurface(
        surface_id="surface.crawler.browser", kind=SurfaceKind.WEB_UI,
        endpoint_ref=None, capabilities=frozenset({"capability.crawl_links"}),
        auth_profile=None, policy_profile_refs=(), static_limits={}, metadata={},
    )
    provider = ProviderSpec(
        provider_id="provider.crawler", version="1.0.0", kind=ProviderKind.CRAWLER,
        display_name="Crawler", domains=(), languages=(), jurisdictions=(),
        surfaces=(surface,), metadata={},
    )
    return provider, surface


def _rule(action):
    return PolicyRule(
        rule_id=f"allow-{action.value}", action=action,
        effect=PolicyRuleEffect.PERMISSION, value=True, asset_scope="*",
        party_scope=None, purpose_scope=("research",), constraints={},
        source_refs=("source1",), priority_hint=1,
    )


def _profile(*rules):
    return SourcePolicyProfile(
        policy_id="policy.test", version="1.0.0",
        provider_id="provider.crawler", surface_id="surface.crawler.browser",
        asset_scope="*", rules=tuple(rules),
        policy_sources=(PolicySourceRef(
            source_id="source1", uri="https://example.com/terms", title="Terms",
            retrieved_at="2026-08-31T00:00:00+00:00", effective_at=None,
            expires_at=None, content_hash=None, anchor={}, authority="provider",
            interpretation_status="human_verified",
        ),), auth_requirements={}, rate_limits={}, retention_rules={},
        attribution_rules={}, redistribution_rules={}, privacy_flags=(),
        observed_at="2026-08-31T00:00:00+00:00", effective_at=None,
        expires_at=None, next_review_at=None, policy_hash="hash",
        review_status="verified", metadata={},
    )


def _context(*actions):
    return PolicyContext(
        task_id="t1", purpose="research", party_profile_id=None,
        risk_class=RiskClass.LOW, jurisdiction_context=(),
        requested_actions=tuple(actions), timestamp="2026-08-31T12:00:00+00:00",
    )


def test_usage_seed_carries_known_downstream_permissions():
    provider, surface = _provider()
    result = DeterministicPolicyEvaluator().evaluate(
        _action(), provider, surface,
        _context(AcquisitionAction.CRAWL),
        profiles=(_profile(
            _rule(AcquisitionAction.CRAWL),
            _rule(AcquisitionAction.INTERNAL_USE),
        ),),
    )
    assert result.authorization.decision is PolicyDecision.ALLOW
    assert AcquisitionAction.CRAWL in result.usage_seed.permissions
    assert AcquisitionAction.INTERNAL_USE in result.usage_seed.permissions


def test_every_requested_action_requires_explicit_permission():
    provider, surface = _provider()
    result = DeterministicPolicyEvaluator().evaluate(
        _action(), provider, surface,
        _context(AcquisitionAction.CRAWL, AcquisitionAction.INTERNAL_USE),
        profiles=(_profile(_rule(AcquisitionAction.CRAWL)),),
    )
    assert result.authorization.decision is PolicyDecision.UNKNOWN
    assert "MISSING_PERMISSION:internal_use" in result.authorization.reason_codes
