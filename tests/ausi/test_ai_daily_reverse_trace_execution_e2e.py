from __future__ import annotations

from dataclasses import dataclass
import runpy

import pytest

from ai_web_research.core.types import ArtifactKind, ArtifactRef, RiskClass, VersionRef
from ai_web_research.domains.ai_industry.live_discovery import (
    build_ai_daily_from_fetched_pages,
    expand_ai_daily_reverse_trace,
)
from ai_web_research.execution.models import ExecutionContext, ObservationStatus, ProviderObservation
from ai_web_research.knowledge.sqlite import KnowledgeStore
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.trace_execution import LEXICAL_METHOD


def _registry():
    provider = ProviderSpec(
        "provider.fake",
        "1.0.0",
        ProviderKind.SEARCH_ENGINE,
        "Fake",
        (),
        (),
        (),
        (
            ProviderSurface(
                "surface.fake",
                SurfaceKind.AUTHENTICATED_API,
                None,
                frozenset({"capability.lexical"}),
                None,
                (),
                {},
                {},
            ),
        ),
        {},
    )
    binding = MethodBinding(
        "binding.fake",
        LEXICAL_METHOD,
        VersionRef("provider.fake", "1.0.0"),
        "surface.fake",
        "adapter.fake",
        "1.0.0",
        True,
        {},
        {},
    )
    return ProviderRegistrySnapshot("snap", (provider,), (binding,))


@dataclass
class Result:
    observation: ProviderObservation


class Runtime:
    async def execute(self, action, context, policy_context, **kwargs):
        query = action.parameters["query"]
        url = (
            "https://official.example/model-x"
            if "available today" in query
            else "https://repo.example/model-x"
        )
        artifact = ArtifactRef(
            ArtifactKind.CANDIDATE,
            "candidate:" + str(abs(hash(query))),
            metadata={
                "url": url,
                "title": "Trace result",
                "description": "search snippet only",
                "provider_rank": 1,
                "evidence_role": "discovery_only",
            },
        )
        return Result(
            ProviderObservation(
                "obs:" + action.action_id,
                action.action_id,
                "provider.fake",
                "surface.fake",
                ObservationStatus.SUCCEEDED,
                (artifact,),
                None,
                1,
                {},
                None,
                {},
                (),
                "2026-09-01T16:01:00Z",
                {"query": query, "evidence_role": "discovery_only"},
            )
        )


@pytest.mark.asyncio
async def test_trace_search_expands_frontier_without_changing_source_graph(tmp_path):
    scenario = runpy.run_path(
        "tests/ausi/fixtures/ai_daily_trace_execution_scenario.py"
    )["build_scenario"]()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    try:
        fetched = build_ai_daily_from_fetched_pages(
            store=store,
            batch_id="batch:trace",
            observation=scenario.observation,
            fetched_pages=scenario.fetched_pages,
            source_nodes=scenario.source_nodes,
            claim_keywords=("Model X", "release"),
            claim_draft=scenario.claim_draft,
            evidence_source_ids=scenario.evidence_source_ids,
            event_draft=scenario.event_draft,
            state=scenario.state,
            budget=scenario.budget,
            policy=scenario.policy,
            generated_at=scenario.state.as_of,
            artifact_id="artifact:trace:zh",
            importance=0.98,
            freshness=1.0,
            audience_relevance=0.95,
            confidence=0.99,
        )
        relations_before = fetched.discovery_result.source_relations
        roots_before = fetched.discovery_result.canonical_claim.independent_root_count
        expanded = await expand_ai_daily_reverse_trace(
            fetched,
            providers=_registry(),
            trusted_runtime=Runtime(),
            execution_context=ExecutionContext(
                "task:trace",
                "epoch:trace",
                "snap",
                services={},
            ),
            policy_context=PolicyContext(
                "task:trace",
                "research",
                None,
                RiskClass.LOW,
                (),
                (AcquisitionAction.AUTOMATED_QUERY,),
                scenario.state.as_of,
            ),
            task_id="task:trace",
            epoch_id="epoch:trace",
            created_at=scenario.state.as_of,
        )
    finally:
        store.close()

    urls = {
        candidate.url
        for batch in expanded.trace_execution_batches
        for execution in batch.executions
        if execution.discovery_batch
        for candidate in execution.discovery_batch.candidates
    }
    assert urls == {
        "https://official.example/model-x",
        "https://repo.example/model-x",
    }
    assert expanded.fetched_result.discovery_result.source_relations == relations_before
    assert (
        expanded.fetched_result.discovery_result.canonical_claim.independent_root_count
        == roots_before
        == 2
    )
    assert all(
        execution.discovery_batch is None
        or all(
            candidate.metadata.get("evidence_role") == "discovery_only"
            for candidate in execution.discovery_batch.candidates
        )
        for batch in expanded.trace_execution_batches
        for execution in batch.executions
    )
