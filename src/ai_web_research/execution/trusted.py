from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import SearchAction
from ai_web_research.evidence.ledger import EvidenceLedger
from ai_web_research.evidence.materialize import (
    materialize_acquired_assets,
    materialize_candidate_evidence,
)
from ai_web_research.evidence.models import CandidateEvidenceMaterialization, MaterializedAsset
from ai_web_research.evidence.store import EvidenceClosureStore
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ProviderObservation
from ai_web_research.execution.runtime import ExecutionRuntime
from ai_web_research.gaps.projection import GapProjection, project_candidate_gaps
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import PolicyContext, PolicyEvaluation, RobotsProfile
from ai_web_research.policy.registry import PolicyRegistrySnapshot
from ai_web_research.providers.registry import ProviderRegistrySnapshot


class TrustedExecutionRejected(RuntimeError):
    def __init__(self, evaluation: PolicyEvaluation) -> None:
        self.evaluation = evaluation
        super().__init__(
            f"trusted execution rejected: {evaluation.authorization.decision}"
        )


@dataclass(frozen=True)
class TrustedExecutionResult:
    policy_evaluation: PolicyEvaluation
    authorized_action: AuthorizedAction
    observation: ProviderObservation
    materialized_assets: tuple[MaterializedAsset, ...]
    candidate_bundles: tuple[CandidateEvidenceMaterialization, ...]
    gap_projections: tuple[GapProjection, ...]


class TrustedExecutionRuntime:
    def __init__(
        self,
        *,
        execution: ExecutionRuntime,
        providers: ProviderRegistrySnapshot,
        policies: PolicyRegistrySnapshot,
        evaluator: DeterministicPolicyEvaluator | None = None,
        store=None,
        receipt_recorder=None,
    ) -> None:
        self.execution = execution
        self.providers = providers
        self.policies = policies
        self.evaluator = evaluator or DeterministicPolicyEvaluator()
        self.store = store
        self.receipt_recorder = receipt_recorder

    async def execute(
        self,
        action: SearchAction,
        context: ExecutionContext,
        policy_context: PolicyContext,
        *,
        robots: RobotsProfile | None = None,
        credential_profile_id: str | None = None,
    ) -> TrustedExecutionResult:
        provider = self.providers.get_provider(action.provider_ref)
        surface = self.providers.surface(action.provider_ref, action.surface_id)
        profiles = self.policies.profiles_for(provider.provider_id, surface.surface_id)

        evaluation = self.evaluator.evaluate(
            action,
            provider,
            surface,
            policy_context,
            profiles,
            robots=robots,
        )
        if not evaluation.authorization.is_executable:
            if self.receipt_recorder is not None:
                self.receipt_recorder.record_rejected(
                    action=action,
                    evaluation=evaluation,
                    occurred_at=policy_context.timestamp,
                )
            raise TrustedExecutionRejected(evaluation)

        authorized = AuthorizedAction(
            action=action,
            authorization=evaluation.authorization,
            credential_profile_id=credential_profile_id,
            usage_seed=evaluation.usage_seed,
        )
        try:
            observation = await self.execution.execute(authorized, context)
        except Exception as exc:
            if self.receipt_recorder is not None:
                self.receipt_recorder.record_failed(
                    action=action,
                    evaluation=evaluation,
                    occurred_at=str(context.services.get("clock") or policy_context.timestamp),
                    exception=exc,
                )
            raise
        materialized_assets = materialize_acquired_assets(authorized, observation)

        candidate_bundles: list[CandidateEvidenceMaterialization] = []
        gap_projections: list[GapProjection] = []

        ledger = EvidenceLedger(self.store) if self.store is not None else None
        if self.store is not None:
            for profile in profiles:
                self.store.save_policy_profile(profile)

        for item in materialized_assets:
            if self.store is not None:
                self.store.save_usage_envelope(item.usage_envelope)
                self.store.save_acquired_asset(item.asset)
            if ledger is not None:
                ledger.append(
                    event_id=item.asset.acquisition_event_id,
                    event_type="ASSET_ACQUIRED",
                    subject_type="asset",
                    subject_id=item.asset.asset_id,
                    actor_id="ausi.trusted_execution",
                    actor_version="0.1.0",
                    input_refs=(action.action_id,),
                    output_refs=(item.asset.asset_id,),
                    payload={
                        "provider_id": item.asset.provider_id,
                        "surface_id": item.asset.surface_id,
                        "usage_envelope_id": item.asset.usage_envelope_id,
                    },
                    created_at=item.asset.retrieved_at,
                )

            bundle = materialize_candidate_evidence(item)
            if not bundle.candidates and not bundle.anchors and not bundle.verifications:
                continue
            candidate_bundles.append(bundle)

            if self.store is not None:
                for anchor in bundle.anchors:
                    self.store.save_anchor(anchor)
                for candidate in bundle.candidates:
                    self.store.save_candidate_evidence(candidate)
                closure_store = EvidenceClosureStore(self.store)
                for verification in bundle.verifications:
                    closure_store.save_verification_result(verification)

            for candidate in bundle.candidates:
                if ledger is not None:
                    ledger.append(
                        event_id=f"{candidate.candidate_evidence_id}:event:created",
                        event_type="EVIDENCE_CANDIDATE_CREATED",
                        subject_type="candidate_evidence",
                        subject_id=candidate.candidate_evidence_id,
                        actor_id="ausi.candidate_materializer",
                        actor_version="0.1.0",
                        input_refs=(candidate.acquired_asset_id,),
                        output_refs=(candidate.candidate_evidence_id,),
                        payload={"field_name": candidate.field_name, "source_type": candidate.source_type},
                        created_at=candidate.created_at,
                    )

                candidate_verifications = tuple(
                    verification
                    for verification in bundle.verifications
                    if verification.evidence_ref == candidate.candidate_evidence_id
                )
                for verification in candidate_verifications:
                    if ledger is not None:
                        event_type = (
                            "ANCHOR_VERIFIED"
                            if verification.decision.value == "pass"
                            else "ANCHOR_FAILED"
                        )
                        ledger.append(
                            event_id=f"{verification.verification_id}:event",
                            event_type=event_type,
                            subject_type="candidate_evidence",
                            subject_id=candidate.candidate_evidence_id,
                            actor_id=verification.verifier_id,
                            actor_version=verification.verifier_version,
                            input_refs=verification.input_refs,
                            output_refs=verification.output_refs,
                            payload={
                                "dimension": verification.dimension.value,
                                "decision": verification.decision.value,
                                "reason_codes": list(verification.reason_codes),
                            },
                            created_at=verification.created_at,
                        )

                projection = project_candidate_gaps(
                    candidate,
                    candidate_verifications,
                    policy_restricted=False,
                    require_source_identity=True,
                    require_version=False,
                    created_at=observation.occurred_at,
                )
                gap_projections.append(projection)
                if self.store is not None:
                    self.store.save_gap_projection(projection)
                if ledger is not None and projection.gap_types:
                    ledger.append(
                        event_id=f"{projection.gap_projection_id}:event",
                        event_type="GAP_PROJECTED",
                        subject_type="gap_projection",
                        subject_id=projection.gap_projection_id,
                        actor_id="ausi.gap_projection",
                        actor_version="0.1.0",
                        input_refs=(candidate.candidate_evidence_id,),
                        output_refs=(projection.gap_projection_id,),
                        payload={
                            "gap_types": [gap.value for gap in projection.gap_types],
                            "reason_codes": list(projection.reason_codes),
                        },
                        created_at=projection.created_at,
                    )

        final_gaps = tuple(gap_projections)
        if self.receipt_recorder is not None:
            self.receipt_recorder.record_success(
                action=action,
                evaluation=evaluation,
                observation=observation,
                gap_projections=final_gaps,
            )

        return TrustedExecutionResult(
            policy_evaluation=evaluation,
            authorized_action=authorized,
            observation=observation,
            materialized_assets=materialized_assets,
            candidate_bundles=tuple(candidate_bundles),
            gap_projections=final_gaps,
        )
