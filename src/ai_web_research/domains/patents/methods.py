from __future__ import annotations

from ai_web_research.core.types import ArtifactKind
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.methods.spec import (
    ContractSpec,
    EvidenceEffect,
    InteractionMode,
    MethodAvailability,
    MethodGoal,
    RepresentationKind,
    SearchDirection,
    SearchMethodSpec,
)


def register_patent_methods(registry: SearchMethodRegistry) -> None:
    registry.register(
        SearchMethodSpec(
            method_id="method.patent.classification_search",
            version="1.0.0",
            availability=MethodAvailability.AVAILABLE,
            aliases=("patent_classification_search",),
            purpose="Search patent candidates through a versioned patent classification symbol.",
            goals=frozenset({MethodGoal.DISCOVER, MethodGoal.NARROW}),
            representations=frozenset({RepresentationKind.TAXONOMY}),
            directions=frozenset({SearchDirection.OUTWARD}),
            interaction_modes=frozenset({InteractionMode.ONE_SHOT, InteractionMode.ITERATIVE}),
            evidence_effects=frozenset({EvidenceEffect.CANDIDATE, EvidenceEffect.METADATA}),
            input_contract=ContractSpec(accepts=frozenset({ArtifactKind.QUERY})),
            output_contract=ContractSpec(produces=frozenset({ArtifactKind.CANDIDATE_SET})),
            parameter_schema={
                "type": "object",
                "properties": {
                    "classification": {"type": "string"},
                    "scheme": {"type": "string", "enum": ["ipc", "cpc"]},
                    "range": {"type": "string"},
                },
                "required": ["classification", "scheme"],
            },
            required_capabilities=frozenset({"capability.taxonomy_filter"}),
            preconditions=("classification_symbol_known",),
            postconditions=("patent_candidate_set_created",),
            failure_modes=(),
            cost_prior={},
            latency_prior={},
            receipt_requirements=("classification", "scheme"),
            stopping_implications=(),
            metadata={"domain": "patent_intelligence"},
        )
    )
