from __future__ import annotations

from ai_web_research.core.types import ArtifactKind
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.methods.spec import ContractSpec, EvidenceEffect, InteractionMode, MethodAvailability, MethodGoal, RepresentationKind, SearchDirection, SearchMethodSpec


def _spec(method_id, purpose, goal, representation, produces, capability, parameters):
    return SearchMethodSpec(
        method_id=method_id,
        version="1.0.0",
        availability=MethodAvailability.AVAILABLE,
        aliases=(),
        purpose=purpose,
        goals=frozenset({goal}),
        representations=frozenset({representation}),
        directions=frozenset({SearchDirection.OUTWARD}),
        interaction_modes=frozenset({InteractionMode.ONE_SHOT}),
        evidence_effects=frozenset({EvidenceEffect.METADATA}),
        input_contract=ContractSpec(accepts=frozenset({ArtifactKind.CANDIDATE, ArtifactKind.DOCUMENT_REF})),
        output_contract=ContractSpec(produces=frozenset({produces})),
        parameter_schema=parameters,
        required_capabilities=frozenset({capability}),
        preconditions=("publication_identity_known",),
        postconditions=(),
        failure_modes=(),
        cost_prior={},
        latency_prior={},
        receipt_requirements=(),
        stopping_implications=(),
        metadata={"domain": "patent_intelligence"},
    )


def register_prior_art_methods(registry: SearchMethodRegistry) -> None:
    registry.register(_spec(
        "method.patent.family_resolve",
        "Resolve an INPADOC extended family.",
        MethodGoal.RELATE,
        RepresentationKind.GRAPH,
        ArtifactKind.STRUCTURED_RECORD,
        "capability.patent_family",
        {"type": "object", "properties": {"docdb_publication": {"type": "string"}}, "required": ["docdb_publication"]},
    ))
    registry.register(_spec(
        "method.patent.claims_fetch",
        "Retrieve machine-readable patent claims.",
        MethodGoal.VERIFY,
        RepresentationKind.STRUCTURED,
        ArtifactKind.DOCUMENT,
        "capability.patent_claims_fulltext",
        {"type": "object", "properties": {"epodoc_publication": {"type": "string"}, "publication_number": {"type": "string"}}, "required": ["epodoc_publication"]},
    ))
