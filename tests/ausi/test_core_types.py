from dataclasses import FrozenInstanceError

import pytest

from ai_web_research.core.types import (
    ActionKind,
    ArtifactKind,
    ArtifactRef,
    RiskClass,
    SearchAction,
    SearchIntent,
    SearchTask,
    VersionRef,
)


def test_version_ref_is_frozen_and_hashable():
    ref = VersionRef(id="method.identity_search", version="1.0.0")
    assert {ref} == {VersionRef(id="method.identity_search", version="1.0.0")}
    with pytest.raises(FrozenInstanceError):
        ref.version = "2.0.0"  # type: ignore[misc]


def test_search_task_keeps_typed_intent_and_risk():
    task = SearchTask(
        task_id="task-1",
        raw_request="find the exact document",
        intent=SearchIntent.RESOLVE_IDENTITY,
        domain=None,
        purpose=None,
        languages=("en",),
        jurisdictions=(),
        freshness={},
        coverage_requirements={},
        verification_requirements={},
        source_preferences=(),
        risk_class=RiskClass.LOW,
        budget={"max_actions": 3},
        domain_pack=None,
        metadata={},
    )
    assert task.intent is SearchIntent.RESOLVE_IDENTITY
    assert task.risk_class is RiskClass.LOW


def test_search_action_references_artifacts_and_versions():
    action = SearchAction(
        action_id="action-1",
        task_id="task-1",
        epoch_id="epoch-1",
        method_ref=VersionRef("method.identity_search", "1.0.0"),
        provider_ref=VersionRef("provider.local_corpus", "1.0.0"),
        surface_id="surface.local.sqlite",
        binding_id="binding.identity_search.local_corpus.v1",
        action_kind=ActionKind.SEARCH,
        inputs=(ArtifactRef(kind=ArtifactKind.QUERY, id="query-1"),),
        parameters={"query": "needle"},
        guards=(),
        expected_effects=("candidate_set_created",),
        created_by="planner.rule.v0",
        created_at="2026-08-31T07:00:00+00:00",
    )
    assert action.inputs[0].kind is ArtifactKind.QUERY
    assert action.method_ref.id == "method.identity_search"
