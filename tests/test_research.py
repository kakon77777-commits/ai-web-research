import json

import httpx

from crawler.llm import LlmConfig
from crawler.research import (
    DivergenceSettings,
    compress,
    diverge,
)


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _config() -> LlmConfig:
    return LlmConfig(provider="anthropic", api_key="test-key", model="claude-haiku-4-5-20251001")


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


# -- diverge() ----------------------------------------------------------------


async def test_diverge_parses_branches_by_category():
    payload = {
        "branches": {
            "semantic": ["a", "b"],
            "task": ["c"],
            "source": ["d", "e"],
            "language": ["f"],
            "perspective": ["g"],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await diverge("AI personal portal", _config(), client=client)

    assert result.seed == "AI personal portal"
    assert result.branches["semantic"] == ["a", "b"]
    assert result.branches["source"] == ["d", "e"]
    assert set(result.branches.keys()) == set(DivergenceSettings().categories)


async def test_diverge_respects_custom_categories():
    payload = {"branches": {"semantic": ["x"], "task": ["y"], "ignored_extra": ["z"]}}

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    settings = DivergenceSettings(categories=("semantic", "task"))
    async with _mock_client(handler) as client:
        result = await diverge("topic", _config(), settings=settings, client=client)

    assert set(result.branches.keys()) == {"semantic", "task"}


async def test_diverge_handles_missing_category_gracefully():
    payload = {"branches": {"semantic": ["only this"]}}

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await diverge("topic", _config(), client=client)

    assert result.branches["semantic"] == ["only this"]
    assert "task" not in result.branches


# -- compress() -----------------------------------------------------------


FINDINGS = [
    {"branch": "technical", "url": "https://a.example/", "key_claim": "A", "stance": "supports", "relevance": "r1"},
    {"branch": "business", "url": "https://b.example/", "key_claim": "B", "stance": "neutral", "relevance": "r2"},
]


async def test_compress_builds_clusters_from_known_urls():
    payload = {
        "core_proposition": "Core finding.",
        "clusters": [
            {"label": "Tech", "summary": "s1", "source_urls": ["https://a.example/"]},
        ],
        "next_queries": ["next one"],
        "unresolved_conflicts": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await compress("seed topic", FINDINGS, _config(), client=client)

    assert result.core_proposition == "Core finding."
    assert result.clusters[0].label == "Tech"
    assert result.clusters[0].source_urls == ["https://a.example/"]
    assert result.next_queries == ["next one"]
    assert result.validation_errors == []


async def test_compress_flags_hallucinated_urls():
    payload = {
        "core_proposition": "Core finding.",
        "clusters": [
            {"label": "Tech", "summary": "s1", "source_urls": ["https://a.example/", "https://not-a-real-source.example/"]},
        ],
        "next_queries": [],
        "unresolved_conflicts": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await compress("seed topic", FINDINGS, _config(), client=client)

    assert result.clusters[0].source_urls == ["https://a.example/"]  # bad URL dropped
    assert len(result.validation_errors) == 1
    assert "not-a-real-source.example" in result.validation_errors[0]


async def test_compress_strips_json_fence():
    payload = {"core_proposition": "P", "clusters": [], "next_queries": [], "unresolved_conflicts": ["c1"]}
    fenced = "```json\n" + json.dumps(payload) + "\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(fenced)

    async with _mock_client(handler) as client:
        result = await compress("seed", FINDINGS, _config(), client=client)

    assert result.core_proposition == "P"
    assert result.unresolved_conflicts == ["c1"]


async def test_compress_to_dict_roundtrips_via_json():
    payload = {
        "core_proposition": "P",
        "clusters": [{"label": "L", "summary": "S", "source_urls": ["https://a.example/"]}],
        "next_queries": ["q"],
        "unresolved_conflicts": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await compress("seed", FINDINGS, _config(), client=client)

    as_json = json.dumps(result.to_dict())
    reloaded = json.loads(as_json)
    assert reloaded["core_proposition"] == "P"
    assert reloaded["clusters"][0]["source_urls"] == ["https://a.example/"]
