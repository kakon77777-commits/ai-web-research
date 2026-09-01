from __future__ import annotations

from ai_web_research.core.types import ArtifactKind
from .registry import SearchMethodRegistry
from .spec import (
    ContractSpec,
    EvidenceEffect,
    InteractionMode,
    MethodAvailability,
    MethodGoal,
    RepresentationKind,
    SearchDirection,
    SearchMethodSpec,
)


def _spec(
    method_id: str,
    availability: MethodAvailability,
    capability: str | frozenset[str],
    accepts: frozenset[ArtifactKind],
    produces: frozenset[ArtifactKind],
    *,
    goal: MethodGoal = MethodGoal.DISCOVER,
    representation: RepresentationKind = RepresentationKind.LEXICAL,
    evidence_effect: EvidenceEffect = EvidenceEffect.CANDIDATE,
) -> SearchMethodSpec:
    return SearchMethodSpec(
        method_id=method_id,
        version="1.0.0",
        availability=availability,
        aliases=(),
        purpose=method_id.removeprefix("method.").replace("_", " "),
        goals=frozenset({goal}),
        representations=frozenset({representation}),
        directions=frozenset({SearchDirection.OUTWARD}),
        interaction_modes=frozenset({InteractionMode.ONE_SHOT}),
        evidence_effects=frozenset({evidence_effect}),
        input_contract=ContractSpec(accepts=accepts),
        output_contract=ContractSpec(produces=produces),
        parameter_schema=(
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }
            if ArtifactKind.QUERY in accepts
            else {"type": "object", "properties": {}}
        ),
        required_capabilities=(capability if isinstance(capability, frozenset) else frozenset({capability})),
        preconditions=(),
        postconditions=(),
        failure_modes=(),
        cost_prior={},
        latency_prior={},
        receipt_requirements=(),
        stopping_implications=(),
        metadata={},
    )


def register_builtin_methods(registry: SearchMethodRegistry) -> None:
    specs = (
        _spec("method.query_divergence", MethodAvailability.AVAILABLE, "capability.llm_generate", frozenset({ArtifactKind.QUERY}), frozenset({ArtifactKind.QUERY_SET}), goal=MethodGoal.EXPAND),
        _spec("method.identity_search", MethodAvailability.AVAILABLE, frozenset({"capability.lexical", "capability.identity_fold"}), frozenset({ArtifactKind.QUERY}), frozenset({ArtifactKind.CANDIDATE_SET}), goal=MethodGoal.LOCATE),
        _spec("method.lexical_search", MethodAvailability.AVAILABLE, "capability.lexical", frozenset({ArtifactKind.QUERY}), frozenset({ArtifactKind.CANDIDATE_SET})),
        _spec("method.crawl_discovery", MethodAvailability.AVAILABLE, "capability.crawl_links", frozenset({ArtifactKind.SEED}), frozenset({ArtifactKind.CANDIDATE_SET}), goal=MethodGoal.DISCOVER),
        _spec("method.fetch_document", MethodAvailability.AVAILABLE, "capability.fetch_url", frozenset({ArtifactKind.DOCUMENT_REF, ArtifactKind.CANDIDATE}), frozenset({ArtifactKind.DOCUMENT}), goal=MethodGoal.LOCATE),
        _spec("method.llm_recall", MethodAvailability.AVAILABLE, "capability.llm_generate", frozenset({ArtifactKind.QUERY}), frozenset({ArtifactKind.CANDIDATE_SET}), goal=MethodGoal.DISCOVER, evidence_effect=EvidenceEffect.NONE),
        _spec("method.extract_candidate_evidence", MethodAvailability.AVAILABLE, "capability.extract_structured", frozenset({ArtifactKind.DOCUMENT}), frozenset({ArtifactKind.EVIDENCE_CANDIDATE}), goal=MethodGoal.VERIFY),
        _spec("method.semantic_search", MethodAvailability.UNAVAILABLE, "capability.semantic", frozenset({ArtifactKind.QUERY}), frozenset({ArtifactKind.CANDIDATE_SET}), representation=RepresentationKind.SEMANTIC),
        _spec("method.forward_citation", MethodAvailability.UNAVAILABLE, "capability.citation_forward", frozenset({ArtifactKind.DOCUMENT_REF}), frozenset({ArtifactKind.CANDIDATE_SET}), representation=RepresentationKind.GRAPH),
        _spec("method.backward_citation", MethodAvailability.UNAVAILABLE, "capability.citation_backward", frozenset({ArtifactKind.DOCUMENT_REF}), frozenset({ArtifactKind.CANDIDATE_SET}), representation=RepresentationKind.GRAPH),
        _spec("method.temporal_version_search", MethodAvailability.UNAVAILABLE, "capability.version_search", frozenset({ArtifactKind.DOCUMENT_REF}), frozenset({ArtifactKind.CANDIDATE_SET}), goal=MethodGoal.RECONCILE, representation=RepresentationKind.TEMPORAL, evidence_effect=EvidenceEffect.VERSION),
        _spec("method.counter_evidence_search", MethodAvailability.PARTIAL, "capability.counter_search", frozenset({ArtifactKind.CLAIM}), frozenset({ArtifactKind.CANDIDATE_SET}), goal=MethodGoal.FALSIFY, evidence_effect=EvidenceEffect.CONTRADICTION),
    )
    for spec in specs:
        registry.register(spec)
