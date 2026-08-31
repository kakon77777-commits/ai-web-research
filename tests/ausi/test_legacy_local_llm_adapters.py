from dataclasses import dataclass

import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.providers.legacy.local import LegacyIdentitySearchAdapter, LegacyLexicalSearchAdapter
from ai_web_research.providers.legacy.llm import LegacyDivergenceAdapter, LegacyLlmRecallAdapter


@dataclass
class FakePath:
    view: str
    retriever: str
    branch_type: str
    branch_text: str
    score: float


@dataclass
class FakeObject:
    document_id: str
    url: str
    title: str | None
    has_exact: bool
    max_score: float
    paths: list[FakePath]


@dataclass
class FakeIdentityResult:
    query: str
    branches: list[str]
    objects: list[FakeObject]
    per_branch: list[dict]


@dataclass
class FakeDivergenceResult:
    seed: str
    branches: dict[str, list[str]]


@dataclass
class FakeRecallFinding:
    branch: str
    queries: list[str]
    answer: str
    model: str


def make_action(method_id, provider_id, surface_id, binding_id, kind, query="alpha"):
    return AuthorizedAction(
        SearchAction(
            action_id=f"a:{method_id}",
            task_id="t1",
            epoch_id="e1",
            method_ref=VersionRef(method_id, "1.0.0"),
            provider_ref=VersionRef(provider_id, "1.0.0"),
            surface_id=surface_id,
            binding_id=binding_id,
            action_kind=kind,
            inputs=(ArtifactRef(ArtifactKind.QUERY, "q1"),),
            parameters={"query": query},
            guards=(),
            expected_effects=(),
            created_by="test",
            created_at="2026-08-31T09:00:00+00:00",
        ),
        AuthorizationResult(PolicyDecision.ALLOW),
    )


def context(**services):
    return ExecutionContext("t1", "e1", "snap", services=services)


@pytest.mark.asyncio
async def test_identity_adapter_maps_folded_objects_and_paths_to_candidates():
    calls = []

    async def fake_search(seed_query, store, llm_config=None, **kwargs):
        calls.append((seed_query, store, kwargs))
        return FakeIdentityResult(
            query=seed_query,
            branches=["original"],
            objects=[FakeObject(
                "doc-1", "https://example.com/a", "Alpha", True, 0.9,
                [FakePath("document", "exact", "original", seed_query, 0.9)],
            )],
            per_branch=[{"branch_type": "original", "hit_count": 1}],
        )

    adapter = LegacyIdentitySearchAdapter(search_fn=fake_search)
    obs = await adapter.execute(
        make_action(
            "method.identity_search", "provider.local_corpus", "surface.local.sqlite",
            "binding.identity_search.local_corpus.v1", ActionKind.RESOLVE_IDENTITY,
        ),
        context(page_store="STORE"),
    )
    assert calls[0][0] == "alpha"
    assert calls[0][1] == "STORE"
    assert obs.artifacts[0].kind is ArtifactKind.CANDIDATE
    assert obs.artifacts[0].id == "doc-1"
    assert obs.artifacts[0].metadata["has_exact"] is True
    assert obs.artifacts[0].metadata["paths"][0]["retriever"] == "exact"
    assert obs.result_count == 1


@pytest.mark.asyncio
async def test_lexical_adapter_forces_single_original_branch():
    seen = {}

    async def fake_search(seed_query, store, llm_config=None, **kwargs):
        seen.update(kwargs)
        return FakeIdentityResult(seed_query, ["original"], [], [])

    adapter = LegacyLexicalSearchAdapter(search_fn=fake_search)
    obs = await adapter.execute(
        make_action(
            "method.lexical_search", "provider.local_corpus", "surface.local.sqlite",
            "binding.lexical_search.local_corpus.v1", ActionKind.SEARCH,
        ),
        context(page_store="STORE"),
    )
    assert seen["use_divergence"] is False
    assert obs.result_count == 0


@pytest.mark.asyncio
async def test_divergence_adapter_returns_query_set_artifact():
    async def fake_diverge(seed, llm_config, **kwargs):
        assert llm_config == "LLM"
        return FakeDivergenceResult(seed, {"semantic": ["alpha synonym"], "source": ["alpha docs"]})

    adapter = LegacyDivergenceAdapter(diverge_fn=fake_diverge)
    obs = await adapter.execute(
        make_action(
            "method.query_divergence", "provider.llm_recall", "surface.llm.vertex",
            "binding.query_divergence.llm.v1", ActionKind.QUERY_TRANSFORM,
        ),
        context(llm_config="LLM"),
    )
    assert len(obs.artifacts) == 1
    assert obs.artifacts[0].kind is ArtifactKind.QUERY_SET
    assert obs.artifacts[0].metadata["branches"]["semantic"] == ["alpha synonym"]


@pytest.mark.asyncio
async def test_llm_recall_is_explicitly_non_external_evidence():
    async def fake_recall(seed, branch, queries, llm_config=None, **kwargs):
        assert llm_config == "LLM"
        return FakeRecallFinding(branch, queries, "Prior-memory answer", "gemini-test")

    adapter = LegacyLlmRecallAdapter(recall_fn=fake_recall)
    obs = await adapter.execute(
        make_action(
            "method.llm_recall", "provider.llm_recall", "surface.llm.vertex",
            "binding.llm_recall.llm.v1", ActionKind.SEARCH,
        ),
        context(llm_config="LLM"),
    )
    artifact = obs.artifacts[0]
    assert artifact.kind is ArtifactKind.CANDIDATE
    assert artifact.metadata["source_type"] == "llm_recall"
    assert artifact.metadata["external_evidence"] is False
    assert artifact.metadata["answer"] == "Prior-memory answer"
