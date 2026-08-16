import json

import httpx

from crawler.llm import LlmConfig
from crawler.research import (
    BASIC_SEARCH_MODEL,
    DivergenceSettings,
    basic_ai_search,
    basic_search_llm_config,
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


# -- basic_ai_search() / basic_search_llm_config() ------------------------------


def test_basic_search_llm_config_overrides_model_on_vertex_base():
    base = LlmConfig(
        provider="vertex", model="gemini-2.5-flash-lite", vertex_project="p",
        vertex_location="us-central1", vertex_credentials_path="/fake/key.json",
    )
    cfg = basic_search_llm_config(base)
    assert cfg.model == BASIC_SEARCH_MODEL
    assert cfg.provider == "vertex"
    assert cfg.vertex_project == "p"


def test_basic_search_llm_config_forces_global_region_and_larger_token_budget():
    # Both gemini-3.5-flash and gemini-3.7-flash 404 in us-central1 for
    # this project — confirmed live; only 'global' works. This model
    # family is also a 'thinking' generation that spends part of its
    # output budget on internal reasoning before emitting visible text —
    # confirmed live that the default max_tokens (1024) truncates a real
    # substantive answer mid-JSON, so this must bump it, not just
    # override model/location.
    base = LlmConfig(
        provider="vertex", model="gemini-2.5-flash-lite", vertex_project="p",
        vertex_location="us-central1", vertex_credentials_path="/fake/key.json",
    )
    cfg = basic_search_llm_config(base)
    assert cfg.vertex_location == "global"
    assert cfg.max_tokens == 4096


def test_basic_search_llm_config_switches_to_vertex_when_available(monkeypatch):
    monkeypatch.setenv("VERTEX_PROJECT_ID", "p")
    monkeypatch.setenv("VERTEX_CREDENTIALS_PATH", "/fake/key.json")
    base = LlmConfig(provider="anthropic", api_key="k", model="claude-haiku-4-5-20251001")

    cfg = basic_search_llm_config(base)
    assert cfg.provider == "vertex"
    assert cfg.model == BASIC_SEARCH_MODEL


def test_basic_search_llm_config_keeps_non_vertex_if_no_vertex_configured(monkeypatch):
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("VERTEX_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    base = LlmConfig(provider="anthropic", api_key="k", model="claude-haiku-4-5-20251001")

    cfg = basic_search_llm_config(base)
    assert cfg.provider == "anthropic"
    assert cfg.model == BASIC_SEARCH_MODEL


async def test_basic_ai_search_returns_recall_finding(monkeypatch):
    # basic_ai_search()'s config always prefers vertex if configured (see
    # basic_search_llm_config) — this machine's real .env has real Vertex
    # credentials, and the vertex provider ignores the injected httpx
    # client entirely (it uses its own SDK client), so without clearing
    # these env vars this test would make a real network call instead of
    # hitting the mock transport below.
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("VERTEX_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    payload = {"answer": "Known from training data.", "confidence": "medium", "caveat": "may be outdated"}

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await basic_ai_search(
            "seed topic", "task", ["query one", "query two"], _config(), client=client
        )

    assert result.branch == "task"
    assert result.queries == ["query one", "query two"]
    assert result.answer == "Known from training data."
    assert result.model == BASIC_SEARCH_MODEL


# -- compress() -----------------------------------------------------------


FINDINGS = [
    {"branch": "technical", "url": "https://a.example/", "source_type": "web_crawled", "key_claim": "A", "stance": "supports", "relevance": "r1"},
    {"branch": "business", "url": "https://b.example/", "source_type": "web_crawled", "key_claim": "B", "stance": "neutral", "relevance": "r2"},
]


async def test_compress_builds_clusters_from_known_urls():
    payload = {
        "core_proposition": "Core finding.",
        "clusters": [
            {"label": "Tech", "summary": "s1", "status": "well_supported", "source_urls": ["https://a.example/"]},
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
    assert result.clusters[0].status == "well_supported"
    assert result.clusters[0].source_urls == ["https://a.example/"]
    assert result.next_queries == ["next one"]
    assert result.validation_errors == []


async def test_compress_flags_hallucinated_urls():
    payload = {
        "core_proposition": "Core finding.",
        "clusters": [
            {
                "label": "Tech", "summary": "s1", "status": "well_supported",
                "source_urls": ["https://a.example/", "https://not-a-real-source.example/"],
            },
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


async def test_compress_flags_non_standard_status():
    payload = {
        "core_proposition": "Core finding.",
        "clusters": [
            {"label": "Tech", "summary": "s1", "status": "definitely true", "source_urls": ["https://a.example/"]},
        ],
        "next_queries": [],
        "unresolved_conflicts": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await compress("seed topic", FINDINGS, _config(), client=client)

    assert result.clusters[0].status == "definitely true"  # kept as-is, just flagged
    assert any("non-standard status" in e for e in result.validation_errors)


async def test_compress_accepts_all_standard_status_values():
    from crawler.research import STATUS_VALUES

    for status in STATUS_VALUES:
        payload = {
            "core_proposition": "P",
            "clusters": [{"label": "L", "summary": "s", "status": status, "source_urls": []}],
            "next_queries": [],
            "unresolved_conflicts": [],
        }

        def handler(request: httpx.Request, _payload=payload) -> httpx.Response:
            return _anthropic_response(json.dumps(_payload))

        async with _mock_client(handler) as client:
            result = await compress("seed", FINDINGS, _config(), client=client)

        assert result.validation_errors == [], f"status {status!r} should not be flagged"


async def test_compress_strips_json_fence():
    payload = {
        "core_proposition": "P", "clusters": [], "next_queries": [],
        "unresolved_conflicts": ["c1"],
    }
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
        "clusters": [{"label": "L", "summary": "S", "status": "well_supported", "source_urls": ["https://a.example/"]}],
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
    assert reloaded["clusters"][0]["status"] == "well_supported"
    assert reloaded["clusters"][0]["source_urls"] == ["https://a.example/"]
