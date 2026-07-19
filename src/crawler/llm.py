"""Minimal LLM provider abstraction across three paths:

- Anthropic direct API
- any OpenAI-compatible chat-completions endpoint (OpenAI itself, Grok,
  Gemini's OpenAI-compat endpoint, etc.) selected by base_url
- Google Vertex AI (Gemini), auth'd via a service-account key file

The first two mirror the callAiProvider() pattern in eveglyph-editor's
src/ai.js — raw httpx calls, no SDK, symmetric and easy to audit — but read
keys from a local untracked .env instead of browser localStorage since this
runs unattended, not interactively. Vertex is the exception: GCP's
service-account OAuth2 flow isn't worth reimplementing by hand, so that path
uses the official `google-genai` SDK (an optional dependency — see the
`vertex` extra in pyproject.toml) and is lazily imported so the rest of this
module works without it installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_VERTEX_LOCATION = "us-central1"
DEFAULT_VERTEX_MODEL = "gemini-2.5-flash-lite"


class LlmError(Exception):
    pass


class LlmNotConfiguredError(LlmError):
    pass


@dataclass
class LlmConfig:
    provider: str  # "anthropic" | "openai_compatible" | "vertex"
    model: str
    api_key: str | None = None  # anthropic / openai_compatible
    base_url: str | None = None  # openai_compatible only
    vertex_project: str | None = None
    vertex_location: str | None = None
    vertex_credentials_path: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.0


def anthropic_config_from_env() -> LlmConfig | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    return LlmConfig(provider="anthropic", api_key=api_key, model=model)


def openai_compatible_config_from_env() -> LlmConfig | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)
    return LlmConfig(provider="openai_compatible", api_key=api_key, model=model, base_url=base_url)


def vertex_config_from_env() -> LlmConfig | None:
    project = os.environ.get("VERTEX_PROJECT_ID")
    credentials_path = os.environ.get("VERTEX_CREDENTIALS_PATH") or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    if not project or not credentials_path:
        return None
    location = os.environ.get("VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
    model = os.environ.get("VERTEX_MODEL", DEFAULT_VERTEX_MODEL)
    return LlmConfig(
        provider="vertex",
        model=model,
        vertex_project=project,
        vertex_location=location,
        vertex_credentials_path=credentials_path,
    )


_PROVIDER_FACTORIES = {
    "anthropic": anthropic_config_from_env,
    "openai_compatible": openai_compatible_config_from_env,
    "vertex": vertex_config_from_env,
}


def default_config_from_env() -> LlmConfig:
    """Prefers the provider named by LLM_PROVIDER; otherwise the first
    configured provider, checked in the order: anthropic, openai_compatible,
    vertex."""
    preferred = os.environ.get("LLM_PROVIDER")
    if preferred in _PROVIDER_FACTORIES:
        cfg = _PROVIDER_FACTORIES[preferred]()
        if cfg:
            return cfg

    for factory in _PROVIDER_FACTORIES.values():
        cfg = factory()
        if cfg:
            return cfg

    raise LlmNotConfiguredError(
        "No LLM configured: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
        "VERTEX_PROJECT_ID + VERTEX_CREDENTIALS_PATH in .env"
    )


async def complete(
    config: LlmConfig, prompt: str, system: str | None = None, client: httpx.AsyncClient | None = None
) -> str:
    """client is injectable for testing; a real call creates its own."""
    if client is not None:
        return await _dispatch(client, config, prompt, system)
    async with httpx.AsyncClient(timeout=60.0) as owned_client:
        return await _dispatch(owned_client, config, prompt, system)


async def _dispatch(
    client: httpx.AsyncClient, config: LlmConfig, prompt: str, system: str | None
) -> str:
    if config.provider == "anthropic":
        return await _complete_anthropic(client, config, prompt, system)
    if config.provider == "openai_compatible":
        return await _complete_openai_compatible(client, config, prompt, system)
    if config.provider == "vertex":
        return await _complete_vertex(config, prompt, system)
    raise LlmError(f"unknown provider: {config.provider}")


async def _complete_anthropic(
    client: httpx.AsyncClient, config: LlmConfig, prompt: str, system: str | None
) -> str:
    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    resp = await client.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json=payload,
    )
    if resp.status_code != 200:
        raise LlmError(f"Anthropic API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    blocks = data.get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


async def _complete_openai_compatible(
    client: httpx.AsyncClient, config: LlmConfig, prompt: str, system: str | None
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = await client.post(
        f"{config.base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "content-type": "application/json",
        },
        json={
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages,
        },
    )
    if resp.status_code != 200:
        raise LlmError(f"OpenAI-compatible API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _build_vertex_client(config: LlmConfig):
    """Split out from _complete_vertex so tests can monkeypatch just the
    client construction without needing a real service-account file."""
    from google import genai
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(
        config.vertex_credentials_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return genai.Client(
        vertexai=True,
        project=config.vertex_project,
        location=config.vertex_location,
        credentials=credentials,
    )


async def _complete_vertex(config: LlmConfig, prompt: str, system: str | None) -> str:
    try:
        from google.genai import types
    except ImportError as exc:
        raise LlmError(
            "vertex provider requires the optional 'google-genai' dependency: "
            "pip install -e '.[vertex]'"
        ) from exc

    client = _build_vertex_client(config)
    gen_config = types.GenerateContentConfig(
        temperature=config.temperature,
        max_output_tokens=config.max_tokens,
        system_instruction=system,
    )
    resp = await client.aio.models.generate_content(
        model=config.model, contents=prompt, config=gen_config
    )
    return resp.text
