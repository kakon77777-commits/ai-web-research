import json

import httpx

from crawler.llm import LlmConfig
from crawler.semantic_extract import (
    ExtractionError,
    _quote_appears_in,
    _validate_against_schema,
    extract_page,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "content_type": {"type": "string", "enum": ["article", "reference"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "content_type"],
}

MARKDOWN = "# Example Domain\nThis domain is for use in documentation examples."


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _config() -> LlmConfig:
    return LlmConfig(provider="anthropic", api_key="test-key", model="claude-haiku-4-5-20251001")


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


async def test_extract_page_parses_valid_response_and_verifies_quote():
    payload = {
        "summary": {
            "value": "An example domain for documentation.",
            "source_quote": "This domain is for use in documentation examples.",
            "confidence": 0.95,
        },
        "content_type": {"value": "reference", "source_quote": "Example Domain", "confidence": 0.8},
        "tags": {"value": ["example", "documentation"], "source_quote": None, "confidence": 0.5},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await extract_page(MARKDOWN, SCHEMA, _config(), url="https://example.com", client=client)

    assert result.url == "https://example.com"
    assert result.validation_errors == []
    assert result.fields["summary"].value == "An example domain for documentation."
    assert result.fields["summary"].quote_verified is True
    assert result.fields["content_type"].quote_verified is True
    assert result.fields["tags"].value == ["example", "documentation"]
    assert result.fields["tags"].quote_verified is False  # no quote given


async def test_extract_page_flags_unverified_quote():
    payload = {
        "summary": {"value": "Something", "source_quote": "text not actually on the page", "confidence": 0.9},
        "content_type": {"value": "article", "source_quote": "Example Domain", "confidence": 0.9},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(json.dumps(payload))

    async with _mock_client(handler) as client:
        result = await extract_page(MARKDOWN, SCHEMA, _config(), client=client)

    assert result.fields["summary"].quote_verified is False


async def test_extract_page_strips_markdown_code_fence():
    payload = {
        "summary": {"value": "S", "source_quote": "Example Domain", "confidence": 0.9},
        "content_type": {"value": "article", "source_quote": "Example Domain", "confidence": 0.9},
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response(fenced)

    async with _mock_client(handler) as client:
        result = await extract_page(MARKDOWN, SCHEMA, _config(), client=client)

    assert result.fields["summary"].value == "S"


async def test_extract_page_raises_extraction_error_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_response("not json at all")

    async with _mock_client(handler) as client:
        try:
            await extract_page(MARKDOWN, SCHEMA, _config(), client=client)
            assert False, "expected ExtractionError"
        except ExtractionError:
            pass


def test_validate_against_schema_flags_missing_required():
    data = {"content_type": {"value": "article"}}
    errors = _validate_against_schema(data, SCHEMA)
    assert any("summary" in e for e in errors)


def test_validate_against_schema_flags_wrong_type():
    data = {
        "summary": {"value": 123},
        "content_type": {"value": "article"},
    }
    errors = _validate_against_schema(data, SCHEMA)
    assert any("summary" in e and "type" in e for e in errors)


def test_validate_against_schema_flags_enum_violation():
    data = {
        "summary": {"value": "ok"},
        "content_type": {"value": "not-a-valid-choice"},
    }
    errors = _validate_against_schema(data, SCHEMA)
    assert any("content_type" in e for e in errors)


def test_validate_against_schema_passes_valid_data():
    data = {
        "summary": {"value": "ok"},
        "content_type": {"value": "article"},
        "tags": {"value": ["a", "b"]},
    }
    assert _validate_against_schema(data, SCHEMA) == []


def test_quote_appears_in_is_whitespace_and_case_insensitive():
    assert _quote_appears_in("Example   Domain", "# Example\nDomain here") is True
    assert _quote_appears_in("EXAMPLE domain", MARKDOWN) is True
    assert _quote_appears_in("not present anywhere", MARKDOWN) is False
    assert _quote_appears_in(None, MARKDOWN) is False
    assert _quote_appears_in("", MARKDOWN) is False
