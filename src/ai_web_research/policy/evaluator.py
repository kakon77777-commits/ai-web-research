from __future__ import annotations

import datetime as dt

from ai_web_research.core.types import RiskClass, SearchAction
from ai_web_research.execution.models import AuthorizationResult, PolicyDecision
from ai_web_research.providers.spec import ProviderSpec, ProviderSurface

from .models import (
    AcquisitionAction,
    Obligation,
    PolicyContext,
    PolicyEvaluation,
    PolicyLimit,
    PolicyRule,
    PolicyRuleEffect,
    RobotsProfile,
    SourcePolicyProfile,
    UsageEnvelopeSeed,
)


def _parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


class DeterministicPolicyEvaluator:
    evaluator_version = "ausi-policy/0.1.0"

    def _scope_applies(self, rule: PolicyRule, context: PolicyContext) -> bool:
        if rule.purpose_scope and context.purpose not in rule.purpose_scope:
            return False
        if rule.party_scope is not None and rule.party_scope != context.party_profile_id:
            return False
        return True

    def _stale_high_risk(
        self, profiles: tuple[SourcePolicyProfile, ...], context: PolicyContext
    ) -> bool:
        if context.risk_class not in {RiskClass.HIGH, RiskClass.PROFESSIONAL_REVIEW}:
            return False
        now = _parse_time(context.timestamp)
        if now is None:
            return False
        for profile in profiles:
            review = _parse_time(profile.next_review_at)
            expiry = _parse_time(profile.expires_at)
            if (review is not None and review < now) or (expiry is not None and expiry < now):
                return True
        return False

    def evaluate(
        self,
        action: SearchAction,
        provider: ProviderSpec,
        surface: ProviderSurface,
        context: PolicyContext,
        profiles: tuple[SourcePolicyProfile, ...],
        robots: RobotsProfile | None = None,
    ) -> PolicyEvaluation:
        if action.provider_ref.id != provider.provider_id or action.surface_id != surface.surface_id:
            auth = AuthorizationResult(
                PolicyDecision.REVIEW,
                reason_codes=("POLICY_TARGET_MISMATCH",),
            )
            return PolicyEvaluation(auth, UsageEnvelopeSeed(), robots.robots_id if robots else None)

        refs = tuple(profile.ref for profile in profiles)
        if self._stale_high_risk(profiles, context):
            auth = AuthorizationResult(
                PolicyDecision.REVIEW,
                policy_refs=refs,
                reason_codes=("POLICY_STALE",),
            )
            return PolicyEvaluation(auth, UsageEnvelopeSeed(policy_refs=refs), robots.robots_id if robots else None)

        # robots is an operational crawl signal: it can prohibit crawl, but allowance never grants rights.
        if (
            robots is not None
            and robots.allowed is False
            and AcquisitionAction.CRAWL in context.requested_actions
        ):
            auth = AuthorizationResult(
                PolicyDecision.DENY,
                policy_refs=refs,
                reason_codes=("ROBOTS_DISALLOW",),
            )
            return PolicyEvaluation(
                auth,
                UsageEnvelopeSeed(
                    prohibitions=(AcquisitionAction.CRAWL,),
                    policy_refs=refs,
                ),
                robots.robots_id,
            )

        applicable = [
            rule
            for profile in profiles
            for rule in profile.rules
            if self._scope_applies(rule, context)
        ]
        all_prohibitions = [r for r in applicable if r.effect is PolicyRuleEffect.PROHIBITION]
        all_permissions = [r for r in applicable if r.effect is PolicyRuleEffect.PERMISSION]
        all_duties = [r for r in applicable if r.effect is PolicyRuleEffect.DUTY]
        all_constraints = [r for r in applicable if r.effect is PolicyRuleEffect.CONSTRAINT]

        requested = set(context.requested_actions)
        prohibitions = [r for r in all_prohibitions if r.action in requested]
        permissions = [r for r in all_permissions if r.action in requested]

        if prohibitions:
            denied = tuple(sorted({r.action for r in all_prohibitions}, key=str))
            auth = AuthorizationResult(
                PolicyDecision.DENY,
                policy_refs=refs,
                reason_codes=tuple(f"POLICY_PROHIBITION:{r.rule_id}" for r in prohibitions),
            )
            return PolicyEvaluation(
                auth,
                UsageEnvelopeSeed(
                    permissions=tuple(sorted({r.action for r in all_permissions}, key=str)),
                    prohibitions=denied,
                    obligations=tuple(
                        Obligation(
                            obligation_id=rule.rule_id,
                            kind=str(rule.value),
                            parameters=dict(rule.constraints),
                            persists_downstream=True,
                            policy_refs=tuple(rule.source_refs),
                        )
                        for rule in all_duties
                    ),
                    limits=tuple(
                        PolicyLimit(
                            limit_id=rule.rule_id,
                            kind=rule.rule_id,
                            value=rule.value,
                            unit=str(rule.constraints.get("unit")) if rule.constraints.get("unit") is not None else None,
                            window=str(rule.constraints.get("window")) if rule.constraints.get("window") is not None else None,
                            policy_refs=tuple(rule.source_refs),
                        )
                        for rule in all_constraints
                    ),
                    policy_refs=refs,
                ),
                robots.robots_id if robots else None,
            )

        permitted_requested = {r.action for r in permissions}
        missing_permissions = tuple(
            sorted(
                (requested_action for requested_action in requested if requested_action not in permitted_requested),
                key=lambda action: action.value,
            )
        )
        if missing_permissions:
            auth = AuthorizationResult(
                PolicyDecision.UNKNOWN,
                policy_refs=refs,
                reason_codes=tuple(
                    f"MISSING_PERMISSION:{action.value}" for action in missing_permissions
                ),
            )
            return PolicyEvaluation(
                auth,
                UsageEnvelopeSeed(
                    permissions=tuple(sorted({r.action for r in all_permissions}, key=str)),
                    prohibitions=tuple(sorted({r.action for r in all_prohibitions}, key=str)),
                    obligations=tuple(
                        Obligation(
                            obligation_id=rule.rule_id,
                            kind=str(rule.value),
                            parameters=dict(rule.constraints),
                            persists_downstream=True,
                            policy_refs=tuple(rule.source_refs),
                        )
                        for rule in all_duties
                    ),
                    limits=tuple(
                        PolicyLimit(
                            limit_id=rule.rule_id,
                            kind=rule.rule_id,
                            value=rule.value,
                            unit=str(rule.constraints.get("unit")) if rule.constraints.get("unit") is not None else None,
                            window=str(rule.constraints.get("window")) if rule.constraints.get("window") is not None else None,
                            policy_refs=tuple(rule.source_refs),
                        )
                        for rule in all_constraints
                    ),
                    policy_refs=refs,
                ),
                robots.robots_id if robots else None,
            )

        obligation_objs = tuple(
            Obligation(
                obligation_id=rule.rule_id,
                kind=str(rule.value),
                parameters=dict(rule.constraints),
                persists_downstream=True,
                policy_refs=tuple(rule.source_refs),
            )
            for rule in all_duties
        )
        limit_objs = tuple(
            PolicyLimit(
                limit_id=rule.rule_id,
                kind=rule.rule_id,
                value=rule.value,
                unit=str(rule.constraints.get("unit")) if rule.constraints.get("unit") is not None else None,
                window=str(rule.constraints.get("window")) if rule.constraints.get("window") is not None else None,
                policy_refs=tuple(rule.source_refs),
            )
            for rule in all_constraints
        )
        granted = tuple(sorted({r.action for r in all_permissions}, key=str))
        prohibited = tuple(sorted({r.action for r in all_prohibitions}, key=str))
        decision = (
            PolicyDecision.ALLOW_WITH_OBLIGATIONS
            if obligation_objs or limit_objs
            else PolicyDecision.ALLOW
        )
        auth = AuthorizationResult(
            decision,
            obligations=tuple(o.obligation_id for o in obligation_objs),
            limits={limit.limit_id: limit.value for limit in limit_objs},
            policy_refs=refs,
            reason_codes=("EXPLICIT_PERMISSION",),
        )
        seed = UsageEnvelopeSeed(
            permissions=granted,
            prohibitions=prohibited,
            obligations=obligation_objs,
            limits=limit_objs,
            policy_refs=refs,
        )
        return PolicyEvaluation(auth, seed, robots.robots_id if robots else None)
