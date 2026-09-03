from __future__ import annotations

from math import inf

from ai_web_research.core.types import VersionRef
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import ProviderTopology, SurfaceKind
from .models import (
    PolicyFreshness,
    ProviderAvailability,
    RoutingCandidateEvaluation,
    RoutingDecision,
    RoutingPolicy,
)
from .state import ProviderStateSnapshot


class NoEligibleBinding(LookupError):
    def __init__(self, decision: RoutingDecision) -> None:
        super().__init__(f"no eligible binding for {decision.method_ref.id}@{decision.method_ref.version}")
        self.decision = decision


def _preference_index(value, ordered) -> int:
    try:
        return ordered.index(value)
    except ValueError:
        return len(ordered) + 1


class BindingSelector:
    def select(
        self,
        method_ref: VersionRef,
        providers: ProviderRegistrySnapshot,
        states: ProviderStateSnapshot,
        policy: RoutingPolicy,
    ) -> RoutingDecision:
        evaluations: list[tuple[RoutingCandidateEvaluation, tuple]] = []
        bindings = tuple(
            sorted(
                (
                    binding
                    for binding in providers.bindings
                    if binding.enabled and binding.method_ref == method_ref
                ),
                key=lambda binding: binding.binding_id,
            )
        )

        for binding in bindings:
            provider = providers.get_provider(binding.provider_ref)
            surface = providers.surface(binding.provider_ref, binding.surface_id)
            state = states.maybe_get(binding.provider_ref, binding.surface_id)
            reasons: list[str] = []

            if state is None:
                if not policy.allow_unknown_state:
                    reasons.append("MISSING_PROVIDER_STATE")
                if policy.require_credential_for_authenticated and (
                    surface.kind is SurfaceKind.AUTHENTICATED_API or surface.auth_profile is not None
                ):
                    reasons.append("CREDENTIAL_UNKNOWN")
                availability = None
                credential_available = None
                quota_remaining = None
                estimated_cost = None
                estimated_latency_ms = None
                policy_freshness = None
                model_available = None
            else:
                availability = state.availability
                credential_available = state.credential_available
                quota_remaining = state.quota_remaining
                estimated_cost = state.estimated_cost
                estimated_latency_ms = state.estimated_latency_ms
                policy_freshness = state.policy_freshness
                model_available = state.model_available

                if state.availability is ProviderAvailability.UNAVAILABLE:
                    reasons.append("PROVIDER_UNAVAILABLE")
                elif state.availability is ProviderAvailability.DEGRADED and not policy.allow_degraded:
                    reasons.append("PROVIDER_DEGRADED")
                elif state.availability is ProviderAvailability.UNKNOWN and not policy.allow_unknown_state:
                    reasons.append("PROVIDER_AVAILABILITY_UNKNOWN")

                if state.healthy is False:
                    reasons.append("PROVIDER_UNHEALTHY")
                elif state.healthy is None and not policy.allow_unknown_state:
                    reasons.append("PROVIDER_HEALTH_UNKNOWN")

                if policy.require_credential_for_authenticated and (
                    surface.kind is SurfaceKind.AUTHENTICATED_API or surface.auth_profile is not None
                ):
                    if state.credential_available is False:
                        reasons.append("CREDENTIAL_UNAVAILABLE")
                    elif state.credential_available is None:
                        reasons.append("CREDENTIAL_UNKNOWN")

                if policy.require_model_available:
                    if state.model_available is False:
                        reasons.append("MODEL_UNAVAILABLE")
                    elif state.model_available is None and provider.topology is ProviderTopology.MODEL_NATIVE:
                        reasons.append("MODEL_AVAILABILITY_UNKNOWN")

                if state.quota_remaining is not None and state.quota_remaining <= 0:
                    reasons.append("QUOTA_EXHAUSTED")

                if policy.require_fresh_policy_state:
                    if state.policy_freshness is PolicyFreshness.STALE:
                        reasons.append("POLICY_STATE_STALE")
                    elif state.policy_freshness is PolicyFreshness.REVIEW_REQUIRED:
                        reasons.append("POLICY_STATE_REVIEW_REQUIRED")
                    elif state.policy_freshness is PolicyFreshness.UNKNOWN:
                        reasons.append("POLICY_STATE_UNKNOWN")

                missing_capabilities = policy.required_runtime_capabilities - state.runtime_capabilities
                if missing_capabilities:
                    reasons.append("RUNTIME_CAPABILITY_MISSING")

                if (
                    policy.max_estimated_cost is not None
                    and state.estimated_cost is not None
                    and state.estimated_cost > policy.max_estimated_cost
                ):
                    reasons.append("COST_LIMIT_EXCEEDED")

                if (
                    policy.max_estimated_latency_ms is not None
                    and state.estimated_latency_ms is not None
                    and state.estimated_latency_ms > policy.max_estimated_latency_ms
                ):
                    reasons.append("LATENCY_LIMIT_EXCEEDED")

            evaluation = RoutingCandidateEvaluation(
                binding_id=binding.binding_id,
                provider_ref=binding.provider_ref,
                surface_id=binding.surface_id,
                eligible=not reasons,
                reason_codes=tuple(reasons),
                availability=availability,
                credential_available=credential_available,
                quota_remaining=quota_remaining,
                estimated_cost=estimated_cost,
                estimated_latency_ms=estimated_latency_ms,
                policy_freshness=policy_freshness,
                model_available=model_available,
            )

            explicit_binding_rank = _preference_index(binding.binding_id, policy.preferred_binding_ids)
            provider_rank = _preference_index(binding.provider_ref.id, policy.preferred_provider_ids)
            topology_rank = _preference_index(provider.topology, policy.preferred_topologies)
            availability_rank = {
                ProviderAvailability.AVAILABLE: 0,
                ProviderAvailability.DEGRADED: 1,
                ProviderAvailability.UNKNOWN: 2,
                ProviderAvailability.UNAVAILABLE: 3,
                None: 4,
            }[availability]
            rank = (
                explicit_binding_rank if policy.preferred_binding_ids else 0,
                provider_rank if policy.preferred_provider_ids else 0,
                topology_rank if policy.preferred_topologies else 0,
                availability_rank,
                estimated_cost if estimated_cost is not None else inf,
                estimated_latency_ms if estimated_latency_ms is not None else inf,
                binding.provider_ref.id,
                binding.surface_id,
                binding.binding_id,
            )
            evaluations.append((evaluation, rank))

        eligible = [(evaluation, rank) for evaluation, rank in evaluations if evaluation.eligible]
        if eligible:
            selected, _ = min(eligible, key=lambda row: row[1])
            if policy.preferred_binding_ids and selected.binding_id in policy.preferred_binding_ids:
                selection_reason = "SELECTED_BY_BINDING_PREFERENCE"
            elif policy.preferred_provider_ids and selected.provider_ref.id in policy.preferred_provider_ids:
                selection_reason = "SELECTED_BY_PROVIDER_PREFERENCE"
            elif policy.preferred_topologies:
                selection_reason = "SELECTED_BY_TOPOLOGY_PREFERENCE"
            else:
                selection_reason = "SELECTED_BY_DETERMINISTIC_FALLBACK"
            return RoutingDecision(
                method_ref=method_ref,
                routing_policy_id=policy.policy_id,
                provider_registry_snapshot_id=providers.snapshot_id,
                provider_state_snapshot_id=states.snapshot_id,
                selected_binding_id=selected.binding_id,
                selected_provider_ref=selected.provider_ref,
                selected_surface_id=selected.surface_id,
                candidates=tuple(evaluation for evaluation, _ in evaluations),
                reason_codes=(selection_reason,),
            )

        decision = RoutingDecision(
            method_ref=method_ref,
            routing_policy_id=policy.policy_id,
            provider_registry_snapshot_id=providers.snapshot_id,
            provider_state_snapshot_id=states.snapshot_id,
            selected_binding_id=None,
            selected_provider_ref=None,
            selected_surface_id=None,
            candidates=tuple(evaluation for evaluation, _ in evaluations),
            reason_codes=("NO_ELIGIBLE_BINDING",),
        )
        raise NoEligibleBinding(decision)
