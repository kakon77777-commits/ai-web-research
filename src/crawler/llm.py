"""Minimal LLM provider abstraction — Anthropic direct, or any OpenAI-compatible
chat-completions endpoint (OpenAI itself, Grok, Gemini's OpenAI-compat
endpoint, etc.) selected by base_url. Mirrors the callAiProvider() pattern in
eveglyph-editor's src/ai.js, but reads keys from a local untracked .env
instead of browser localStorage since this runs unattended, not interactively.

Deliberately raw httpx calls, no provider SDKs — keeps this dependency-light
and the two branches symmetric and easy to audit.
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


class LlmError(Exception):
    pass


class LlmNotConfiguredError(LlmError):
    pass


@dataclass
class LlmConfig:
    provider: str  # "anthropic" | "openai_compatible"
    api_key: str
    model: str
    base_url: str | None = None  # only used by openai_compatible
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


def default_config_from_env() -> LlmConfig:
    """Prefers the provider named by LLM_PROVIDER; otherwise whichever key is
    present, Anthropic first."""
    preferred = os.environ.get("LLM_PROVIDER")
    if preferred == "anthropic":
        cfg = anthropic_config_from_env()
        if cfg:
            return cfg
    if preferred == "openai_compatible":
        cfg = openai_compatible_config_from_env()
        if cfg:
            return cfg

    cfg = anthropic_config_from_env() or openai_compatible_config_from_env()
    if cfg is None:
        raise LlmNotConfiguredError(
            "No LLM configured: set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
        )
    return cfg


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
