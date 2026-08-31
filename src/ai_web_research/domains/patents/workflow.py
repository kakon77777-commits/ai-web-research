from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.trusted import TrustedExecutionRuntime
from ai_web_research.experience.receipt import SearchReceiptStatus
from ai_web_research.policy.models import AcquisitionAction, PolicyContext

from .coverage import PatentBranchRecord, evaluate_patent_coverage
from .models import InventionFeature, PatentConcept
from .prior_art_materialize import (
    apply_families,
    chronology,
    fold_families,
    npl_candidate,
    patent_candidate,
    patent_claims,
    patent_family,
)


@dataclass(frozen=True)
class SoftwarePriorArtDiscoveryRequest:
    task_id: str
    epoch_id: str
    feature: InventionFeature
    concept: PatentConcept
    classifications: tuple[str, ...]
    classification_scheme: str
    jurisdictions: tuple[str, ...]
    languages: tuple[str, ...]
    cutoff: str | None
    include_npl: bool = True
    include_backward_citation: bool = False
    max_deep_candidates: int = 3
    max_results_per_branch: int = 10


@dataclass(frozen=True)
class SoftwarePriorArtDiscoveryResult:
    patent_candidates: tuple
    family_identities: tuple
    family_folds: tuple
    chronologies: tuple
    claims: tuple
    npl_candidates: tuple
    coverage: object
    status: str
    stop_reason: str
    search_receipt: object | None


class SoftwarePriorArtDiscoveryWorkflow:
    """First deterministic AUSI patent workflow.

    This workflow deliberately stops as PARTIAL while OPS claim fulltext has not
    been reconciled to a legally authoritative publication manifestation.
    """

    def __init__(
        self,
        runtime: TrustedExecutionRuntime,
        context: ExecutionContext,
        epo_credential_profile_id: str = "credential.epo_ops",
    ) -> None:
        self.runtime = runtime
        self.context = context
        self.epo_credential_profile_id = epo_credential_profile_id

    @staticmethod
    def _query(request: SoftwarePriorArtDiscoveryRequest) -> str:
        terms = (
            request.concept.patent_style_terms
            or request.concept.functional_terms
            or (request.feature.description,)
        )
        return " ".join(term for term in terms if term).strip()

    def _policy_context(self, request: SoftwarePriorArtDiscoveryRequest) -> PolicyContext:
        return PolicyContext(
            task_id=request.task_id,
            purpose="research",
            party_profile_id=None,
            risk_class=RiskClass.HIGH,
            jurisdiction_context=request.jurisdictions,
            requested_actions=(AcquisitionAction.AUTOMATED_QUERY,),
            timestamp=str(self.context.services.get("clock") or "2026-08-31T12:00:00+00:00"),
        )

    @staticmethod
    def _action(
        request: SoftwarePriorArtDiscoveryRequest,
        *,
        suffix: str,
        method_id: str,
        provider_id: str,
        provider_version: str,
        surface_id: str,
        binding_id: str,
        action_kind: ActionKind,
        inputs: tuple[ArtifactRef, ...],
        parameters: dict,
    ) -> SearchAction:
        return SearchAction(
            action_id=f"{request.epoch_id}:{suffix}",
            task_id=request.task_id,
            epoch_id=request.epoch_id,
            method_ref=VersionRef(method_id, "1.0.0"),
            provider_ref=VersionRef(provider_id, provider_version),
            surface_id=surface_id,
            binding_id=binding_id,
            action_kind=action_kind,
            inputs=inputs,
            parameters=parameters,
            guards=(),
            expected_effects=("prior_art_state_updated",),
            created_by="workflow.software_prior_art.v0",
            created_at="2026-08-31T12:00:00+00:00",
        )

    async def run(self, request: SoftwarePriorArtDiscoveryRequest) -> SoftwarePriorArtDiscoveryResult:
        policy_context = self._policy_context(request)
        query = self._query(request)
        branches: list[PatentBranchRecord] = []
        patent_artifacts: dict[str, ArtifactRef] = {}

        lexical = self._action(
            request,
            suffix="patent-lexical",
            method_id="method.lexical_search",
            provider_id="provider.epo_ops",
            provider_version="1.1.0",
            surface_id="surface.epo_ops.rest",
            binding_id="binding.lexical_search.epo_ops_prior_art.v1",
            action_kind=ActionKind.SEARCH,
            inputs=(ArtifactRef(ArtifactKind.QUERY, f"{request.epoch_id}:patent-query"),),
            parameters={"query": query, "range": f"1-{request.max_results_per_branch}"},
        )
        result = await self.runtime.execute(
            lexical,
            self.context,
            policy_context,
            credential_profile_id=self.epo_credential_profile_id,
        )
        for artifact in result.observation.artifacts:
            patent_artifacts.setdefault(artifact.id, artifact)
        branches.append(PatentBranchRecord(
            branch_id=lexical.action_id,
            branch_type="FEATURE_BRANCH",
            method_id=lexical.method_ref.id,
            provider_id=lexical.provider_ref.id,
            status="searched",
            features=(request.feature.feature_id,),
            classifications=(),
            jurisdictions=request.jurisdictions,
            languages=request.languages,
            result_count=result.observation.result_count or 0,
        ))

        for index, classification in enumerate(request.classifications, 1):
            action = self._action(
                request,
                suffix=f"classification-{index}",
                method_id="method.patent.classification_search",
                provider_id="provider.epo_ops",
                provider_version="1.1.0",
                surface_id="surface.epo_ops.rest",
                binding_id="binding.patent_classification.epo_ops_prior_art.v1",
                action_kind=ActionKind.SEARCH,
                inputs=(ArtifactRef(ArtifactKind.QUERY, f"{request.epoch_id}:classification:{classification}"),),
                parameters={
                    "classification": classification,
                    "scheme": request.classification_scheme,
                    "range": f"1-{request.max_results_per_branch}",
                },
            )
            result = await self.runtime.execute(
                action,
                self.context,
                policy_context,
                credential_profile_id=self.epo_credential_profile_id,
            )
            for artifact in result.observation.artifacts:
                patent_artifacts.setdefault(artifact.id, artifact)
            branches.append(PatentBranchRecord(
                branch_id=action.action_id,
                branch_type="CLASSIFICATION_BRANCH",
                method_id=action.method_ref.id,
                provider_id=action.provider_ref.id,
                status="searched",
                features=(request.feature.feature_id,),
                classifications=(classification,),
                jurisdictions=request.jurisdictions,
                languages=request.languages,
                result_count=result.observation.result_count or 0,
            ))

        candidates = tuple(patent_candidate(artifact) for artifact in patent_artifacts.values())
        families = []
        claims = []

        for candidate in candidates[: max(0, request.max_deep_candidates)]:
            docdb_publication = candidate.metadata.get("docdb_publication")
            epodoc_publication = candidate.metadata.get("epodoc_publication")

            if docdb_publication:
                action = self._action(
                    request,
                    suffix=f"family-{candidate.publication_number}",
                    method_id="method.patent.family_resolve",
                    provider_id="provider.epo_ops",
                    provider_version="1.1.0",
                    surface_id="surface.epo_ops.rest",
                    binding_id="binding.patent_family.epo_ops_prior_art.v1",
                    action_kind=ActionKind.RESOLVE_IDENTITY,
                    inputs=(ArtifactRef(ArtifactKind.CANDIDATE, candidate.candidate_id),),
                    parameters={"docdb_publication": docdb_publication},
                )
                result = await self.runtime.execute(
                    action,
                    self.context,
                    policy_context,
                    credential_profile_id=self.epo_credential_profile_id,
                )
                if result.observation.artifacts:
                    families.append(patent_family(result.observation.artifacts[0]))

            if epodoc_publication:
                action = self._action(
                    request,
                    suffix=f"claims-{candidate.publication_number}",
                    method_id="method.patent.claims_fetch",
                    provider_id="provider.epo_ops",
                    provider_version="1.1.0",
                    surface_id="surface.epo_ops.rest",
                    binding_id="binding.patent_claims.epo_ops_prior_art.v1",
                    action_kind=ActionKind.FETCH,
                    inputs=(ArtifactRef(ArtifactKind.CANDIDATE, candidate.candidate_id),),
                    parameters={
                        "epodoc_publication": epodoc_publication,
                        "publication_number": candidate.publication_number,
                    },
                )
                result = await self.runtime.execute(
                    action,
                    self.context,
                    policy_context,
                    credential_profile_id=self.epo_credential_profile_id,
                )
                if result.observation.artifacts:
                    claims.extend(patent_claims(result.observation.artifacts[0]))

        candidates = apply_families(candidates, tuple(families))
        npl = []
        if request.include_npl:
            action = self._action(
                request,
                suffix="npl",
                method_id="method.lexical_search",
                provider_id="provider.crossref",
                provider_version="1.0.0",
                surface_id="surface.crossref.rest",
                binding_id="binding.lexical_search.crossref.v1",
                action_kind=ActionKind.SEARCH,
                inputs=(ArtifactRef(ArtifactKind.QUERY, f"{request.epoch_id}:npl-query"),),
                parameters={"query": query, "top_k": request.max_results_per_branch},
            )
            result = await self.runtime.execute(action, self.context, policy_context)
            npl = [npl_candidate(artifact) for artifact in result.observation.artifacts]
            branches.append(PatentBranchRecord(
                branch_id=action.action_id,
                branch_type="NPL_BRANCH",
                method_id=action.method_ref.id,
                provider_id=action.provider_ref.id,
                status="searched",
                features=(request.feature.feature_id,),
                classifications=(),
                jurisdictions=(),
                languages=request.languages,
                result_count=result.observation.result_count or 0,
            ))

        coverage = evaluate_patent_coverage(
            required_features=(request.feature.feature_id,),
            required_classifications=request.classifications,
            required_jurisdictions=request.jurisdictions,
            required_languages=request.languages,
            include_npl=request.include_npl,
            include_backward_citation=request.include_backward_citation,
            authoritative_claim_manifestations_verified=(
                bool(claims) and all(claim.is_legally_authoritative for claim in claims)
            ),
            branches=tuple(branches),
        )
        status = "PARTIAL" if coverage.gaps else "COMPLETE_WITH_DECLARED_SCOPE"
        stop_reason = "MANDATORY_GAPS_REMAIN" if coverage.gaps else status
        receipt = None
        if self.runtime.receipt_recorder is not None:
            receipt = self.runtime.receipt_recorder.finalize(
                receipt_id=f"{request.epoch_id}:prior-art-receipt",
                task_id=request.task_id,
                epoch_id=request.epoch_id,
                registry_snapshot_id=self.context.registry_snapshot_id,
                planner_id="workflow.software_prior_art",
                planner_version="0.1.0",
                stop_reason=stop_reason,
                status=(SearchReceiptStatus.PARTIAL if coverage.gaps else SearchReceiptStatus.COMPLETE),
                created_at=str(self.context.services.get("clock") or "2026-08-31T12:00:10+00:00"),
                metadata={
                    "patent_candidates": len(candidates),
                    "npl_candidates": len(npl),
                    "patent_gaps": [gap.value for gap in coverage.gaps],
                },
            )

        return SoftwarePriorArtDiscoveryResult(
            patent_candidates=candidates,
            family_identities=tuple(families),
            family_folds=fold_families(candidates),
            chronologies=tuple(chronology(candidate, request.cutoff) for candidate in candidates),
            claims=tuple(claims),
            npl_candidates=tuple(npl),
            coverage=coverage,
            status=status,
            stop_reason=stop_reason,
            search_receipt=receipt,
        )
