import httpx
import pytest

from crawler.llm import (
    LlmConfig,
    LlmError,
    LlmNotConfiguredError,
    anthropic_config_from_env,
    complete,
    default_config_from_env,
    openai_compatible_config_from_env,
)


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_anthropic_complete_extracts_text_blocks():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["anthropic-version"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello from claude"}]})

    config = LlmConfig(provider="anthropic", api_key="test-key", model="claude-haiku-4-5-20251001")
    async with _mock_client(handler) as client:
        result = await complete(config, "hi", client=client)
    assert result == "hello from claude"


async def test_anthropic_complete_sends_system_prompt():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    config = LlmConfig(provider="anthropic", api_key="k", model="m")
    async with _mock_client(handler) as client:
        await complete(config, "hi", system="be terse", client=client)
    assert captured["body"]["system"] == "be terse"


async def test_anthropic_complete_raises_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    config = LlmConfig(provider="anthropic", api_key="bad", model="m")
    async with _mock_client(handler) as client:
        with pytest.raises(LlmError):
            await complete(config, "hi", client=client)


async def test_openai_compatible_complete_extracts_message_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello from gpt"}}]})

    config = LlmConfig(
        provider="openai_compatible", api_key="test-key", model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    )
    async with _mock_client(handler) as client:
        result = await complete(config, "hi", client=client)
    assert result == "hello from gpt"


async def test_openai_compatible_works_against_any_base_url():
    """Grok/Gemini's OpenAI-compatible endpoints are just a different base_url."""
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    config = LlmConfig(
        provider="openai_compatible", api_key="k", model="grok-4.5", base_url="https://api.x.ai/v1"
    )
    async with _mock_client(handler) as client:
        await complete(config, "hi", client=client)
    assert seen_urls == ["https://api.x.ai/v1/chat/completions"]


async def test_openai_compatible_raises_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    config = LlmConfig(provider="openai_compatible", api_key="k", model="m", base_url="https://api.openai.com/v1")
    async with _mock_client(handler) as client:
        with pytest.raises(LlmError):
            await complete(config, "hi", client=client)


async def test_complete_raises_on_unknown_provider():
    config = LlmConfig(provider="not-a-real-provider", api_key="k", model="m")
    async with httpx.AsyncClient() as client:
        with pytest.raises(LlmError):
            await complete(config, "hi", client=client)


def test_anthropic_config_from_env_reads_key_and_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "abc")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    cfg = anthropic_config_from_env()
    assert cfg.api_key == "abc"
    assert cfg.model == "claude-opus-4-8"


def test_anthropic_config_from_env_none_when_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert anthropic_config_from_env() is None


def test_openai_compatible_config_from_env_defaults_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "xyz")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    cfg = openai_compatible_config_from_env()
    assert cfg.api_key == "xyz"
    assert cfg.base_url == "https://api.openai.com/v1"


def test_default_config_from_env_prefers_anthropic_when_both_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "abc")
    monkeypatch.setenv("OPENAI_API_KEY", "xyz")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cfg = default_config_from_env()
    assert cfg.provider == "anthropic"


def test_default_config_from_env_respects_explicit_preference(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "abc")
    monkeypatch.setenv("OPENAI_API_KEY", "xyz")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    cfg = default_config_from_env()
    assert cfg.provider == "openai_compatible"


def test_default_config_from_env_raises_when_nothing_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(LlmNotConfiguredError):
        default_config_from_env()
