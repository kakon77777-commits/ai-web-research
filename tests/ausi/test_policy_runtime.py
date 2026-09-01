from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import PolicyDecision
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import (
    AcquisitionAction,
    PolicyContext,
    PolicyRule,
    PolicyRuleEffect,
    PolicySourceRef,
    RobotsProfile,
    SourcePolicyProfile,
)
from ai_web_research.policy.registry import PolicyRegistryVersionConflict, SourcePolicyRegistry
from ai_web_research.providers.spec import ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind


def make_action() -> SearchAction:
    return SearchAction(
        action_id="epoch-1:action:1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.crawl_discovery", "1.0.0"),
        provider_ref=VersionRef("provider.crawler", "1.0.0"),
        surface_id="surface.crawler.browser",
        binding_id="binding.crawl_discovery.crawler.v1",
        action_kind=ActionKind.CRAWL,
        inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
        parameters={"seed_url": "https://example.com"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T12:00:00+00:00",
    )


def make_provider():
    surface = ProviderSurface(
        surface_id="surface.crawler.browser",
        kind=SurfaceKind.WEB_UI,
        endpoint_ref=None,
        capabilities=frozenset({"capability.fetch_url", "capability.crawl_links"}),
        auth_profile=None,
        policy_profile_refs=(),
        static_limits={},
        metadata={},
    )
    provider = ProviderSpec(
        provider_id="provider.crawler",
        version="1.0.0",
        kind=ProviderKind.CRAWLER,
        display_name="Crawler",
        domains=(),
        languages=(),
        jurisdictions=(),
        surfaces=(surface,),
        metadata={},
    )
    return provider, surface


def make_context(risk=RiskClass.LOW, timestamp="2026-08-31T12:00:00+00:00"):
    return PolicyContext(
        task_id="task-1",
        purpose="research",
        party_profile_id=None,
        risk_class=risk,
        jurisdiction_context=(),
        requested_actions=(AcquisitionAction.CRAWL,),
        timestamp=timestamp,
    )


def make_profile(*rules, version="1.0.0", next_review_at=None):
    source = PolicySourceRef(
        source_id="policy-source-1",
        uri="https://example.com/terms",
        title="Terms",
        retrieved_at="2026-08-30T00:00:00+00:00",
        effective_at=None,
        expires_at=None,
        content_hash="abc",
        anchor={},
        authority="provider",
        interpretation_status="human_verified",
    )
    return SourcePolicyProfile(
        policy_id="policy.crawler.example",
        version=version,
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        asset_scope="*",
        rules=tuple(rules),
        policy_sources=(source,),
        auth_requirements={},
        rate_limits={},
        retention_rules={},
        attribution_rules={},
        redistribution_rules={},
        privacy_flags=(),
        observed_at="2026-08-30T00:00:00+00:00",
        effective_at=None,
        expires_at=None,
        next_review_at=next_review_at,
        policy_hash="hash-" + version,
        review_status="verified",
        metadata={},
    )


def permission():
    return PolicyRule(
        rule_id="allow-crawl",
        action=AcquisitionAction.CRAWL,
        effect=PolicyRuleEffect.PERMISSION,
        value=True,
        asset_scope="*",
        party_scope=None,
        purpose_scope=("research",),
        constraints={},
        source_refs=("policy-source-1",),
        priority_hint=10,
    )


def test_registry_rejects_same_version_semantic_conflict():
    registry = SourcePolicyRegistry()
    registry.register(make_profile(permission()))
    conflicting = make_profile(
        PolicyRule(
            rule_id="deny-crawl",
            action=AcquisitionAction.CRAWL,
            effect=PolicyRuleEffect.PROHIBITION,
            value=True,
            asset_scope="*",
            party_scope=None,
            purpose_scope=("research",),
            constraints={},
            source_refs=("policy-source-1",),
            priority_hint=10,
        )
    )
    try:
        registry.register(conflicting)
    except PolicyRegistryVersionConflict:
        pass
    else:
        raise AssertionError("same policy id/version conflict must be rejected")


def test_no_applicable_policy_is_unknown_and_robots_allow_does_not_grant_permission():
    provider, surface = make_provider()
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(), profiles=(),
        robots=RobotsProfile(
            robots_id="robots-1",
            provider_id="provider.crawler",
            surface_id="surface.crawler.browser",
            user_agent="AUSI",
            uri="https://example.com/robots.txt",
            fetched_at="2026-08-31T11:00:00+00:00",
            status_code=200,
            allowed=True,
            crawl_delay_seconds=None,
            content_hash="rhash",
            fetch_status="ok",
        ),
    )
    assert result.authorization.decision is PolicyDecision.UNKNOWN


def test_explicit_prohibition_denies():
    provider, surface = make_provider()
    deny = PolicyRule(
        rule_id="deny-crawl",
        action=AcquisitionAction.CRAWL,
        effect=PolicyRuleEffect.PROHIBITION,
        value=True,
        asset_scope="*",
        party_scope=None,
        purpose_scope=("research",),
        constraints={},
        source_refs=("policy-source-1",),
        priority_hint=20,
    )
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(), profiles=(make_profile(deny),)
    )
    assert result.authorization.decision is PolicyDecision.DENY


def test_permission_only_allows_and_returns_usage_seed():
    provider, surface = make_provider()
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(), profiles=(make_profile(permission()),)
    )
    assert result.authorization.decision is PolicyDecision.ALLOW
    assert AcquisitionAction.CRAWL in result.usage_seed.permissions
    assert result.authorization.policy_refs == ("policy.crawler.example@1.0.0",)


def test_permission_with_duty_and_constraint_is_allow_with_obligations():
    provider, surface = make_provider()
    duty = PolicyRule(
        rule_id="attribute",
        action=AcquisitionAction.CRAWL,
        effect=PolicyRuleEffect.DUTY,
        value="attribute-source",
        asset_scope="*",
        party_scope=None,
        purpose_scope=("research",),
        constraints={},
        source_refs=("policy-source-1",),
        priority_hint=5,
    )
    constraint = PolicyRule(
        rule_id="rate",
        action=AcquisitionAction.CRAWL,
        effect=PolicyRuleEffect.CONSTRAINT,
        value=5,
        asset_scope="*",
        party_scope=None,
        purpose_scope=("research",),
        constraints={"unit": "requests", "window": "second"},
        source_refs=("policy-source-1",),
        priority_hint=5,
    )
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(),
        profiles=(make_profile(permission(), duty, constraint),),
    )
    assert result.authorization.decision is PolicyDecision.ALLOW_WITH_OBLIGATIONS
    assert len(result.usage_seed.obligations) == 1
    assert len(result.usage_seed.limits) == 1


def test_robots_disallow_blocks_crawl_even_when_terms_permit():
    provider, surface = make_provider()
    robots = RobotsProfile(
        robots_id="robots-2",
        provider_id="provider.crawler",
        surface_id="surface.crawler.browser",
        user_agent="AUSI",
        uri="https://example.com/robots.txt",
        fetched_at="2026-08-31T11:00:00+00:00",
        status_code=200,
        allowed=False,
        crawl_delay_seconds=None,
        content_hash="rhash2",
        fetch_status="ok",
    )
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(),
        profiles=(make_profile(permission()),), robots=robots,
    )
    assert result.authorization.decision is PolicyDecision.DENY
    assert "ROBOTS_DISALLOW" in result.authorization.reason_codes


def test_stale_high_risk_policy_requires_review():
    provider, surface = make_provider()
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface,
        make_context(RiskClass.HIGH, "2026-08-31T12:00:00+00:00"),
        profiles=(make_profile(permission(), next_review_at="2026-08-31T00:00:00+00:00"),),
    )
    assert result.authorization.decision is PolicyDecision.REVIEW
    assert "POLICY_STALE" in result.authorization.reason_codes


def test_policy_snapshot_uses_latest_version_per_policy_identity():
    registry = SourcePolicyRegistry()
    old_deny = PolicyRule(
        rule_id="old-deny",
        action=AcquisitionAction.CRAWL,
        effect=PolicyRuleEffect.PROHIBITION,
        value=True,
        asset_scope="*",
        party_scope=None,
        purpose_scope=("research",),
        constraints={},
        source_refs=("policy-source-1",),
        priority_hint=1,
    )
    registry.register(make_profile(old_deny, version="1.0.0"))
    registry.register(make_profile(permission(), version="2.0.0"))
    profiles = registry.snapshot().profiles_for("provider.crawler", "surface.crawler.browser")
    assert [p.version for p in profiles] == ["2.0.0"]

    provider, surface = make_provider()
    result = DeterministicPolicyEvaluator().evaluate(
        make_action(), provider, surface, make_context(), profiles=profiles
    )
    assert result.authorization.decision is PolicyDecision.ALLOW
