"""Semantic extraction (doc1 第十二部分, 階段四：語義抽取).

Given a crawled page's Markdown and a caller-supplied JSON Schema describing
what to extract, asks an LLM (via llm.complete()) to return structured JSON
matching that schema — the Prompt-to-Extraction pattern from doc1 section
11.2. Doc1's own required 驗證規則 is built in as a real safeguard against its
own risk section 12.1 (幻覺/hallucination): every extracted field must also
carry a `source_quote` copied verbatim from the input page, which this module
independently verifies actually appears in that page before trusting it. A
field whose quote can't be found in the source text is flagged
`quote_verified=False` rather than silently trusted — a low-cost, deterministic
check, not another LLM call grading its own homework.

Deliberately does NOT bring in a JSON Schema validation library — the schema
subset used here (`type`, `properties`, `required`, `enum`, `items.type`) is
small enough that hand-rolling the check keeps this module dependency-free,
matching the rest of this codebase (extract.py, store.py use no ORM/
validation frameworks either).

This is a distinct second pass over already-crawled pages, not inlined into
run.py's per-page fetch loop — extraction is LLM-rate-limited and separately
re-runnable (new prompt/model = new EXTRACTOR_VERSION), unlike the
deterministic fetch/parse/store loop it follows.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import AppConfig
from .llm import LlmConfig, complete, default_config_from_env
from .store import ExtractionRecord, PageStore

EXTRACTOR_VERSION = "ai-web-research-stage4/0.1.0"

logger = logging.getLogger("crawler.semantic_extract")

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class ExtractionError(Exception):
    pass


@dataclass
class ExtractedField:
    value: Any
    source_quote: str | None
    confidence: float | None
    quote_verified: bool


@dataclass
class ExtractionResult:
    url: str
    extractor_version: str
    provider: str
    model: str
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class ExtractionStats:
    extracted: int = 0
    skipped_missing_markdown: int = 0
    failed: int = 0


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _system_prompt() -> str:
    return (
        "You are a precise information-extraction engine. You will be given a "
        "JSON Schema describing fields to extract from a webpage's content, and "
        "the page content itself as Markdown. Respond with ONLY a single JSON "
        'object (no prose, no markdown code fences) mapping each schema field '
        'name to an object with exactly three keys: "value" (the extracted '
        "value, matching the field's declared type), \"source_quote\" (a short "
        "verbatim substring copied exactly from the page content that supports "
        'this value — do not paraphrase it), and "confidence" (a number from '
        '0 to 1). If a field\'s value genuinely cannot be found in the page '
        'content, set "value" to null, "source_quote" to null, and '
        '"confidence" to 0.'
    )


def _user_prompt(markdown: str, schema: dict) -> str:
    return (
        f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"Page content (Markdown):\n{markdown}"
    )


def _strip_json_fence(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


def _parse_llm_json(text: str) -> dict:
    cleaned = _strip_json_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"LLM response was not valid JSON: {exc}\n---\n{text[:500]}") from exc
    if not isinstance(data, dict):
        raise ExtractionError(f"LLM response JSON was not an object: {type(data).__name__}")
    return data


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def _validate_value(name: str, value: Any, field_schema: dict) -> list[str]:
    errors: list[str] = []
    expected_type = field_schema.get("type")
    if expected_type and expected_type in _TYPE_CHECKS and not _TYPE_CHECKS[expected_type](value):
        errors.append(f"{name}: expected type {expected_type!r}, got {type(value).__name__}")
        return errors  # further checks assume the type already matches

    enum = field_schema.get("enum")
    if enum and value not in enum:
        errors.append(f"{name}: value {value!r} not in enum {enum!r}")

    if expected_type == "array":
        item_type = field_schema.get("items", {}).get("type")
        if item_type and item_type in _TYPE_CHECKS:
            for item in value:
                if not _TYPE_CHECKS[item_type](item):
                    errors.append(f"{name}: array item {item!r} is not type {item_type!r}")
    return errors


def _validate_against_schema(data: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, field_schema in properties.items():
        entry = data.get(name)
        if not isinstance(entry, dict):
            if name in required:
                errors.append(f"{name}: required field missing or malformed")
            continue
        value = entry.get("value")
        if value is None:
            if name in required:
                errors.append(f"{name}: required field is null")
            continue
        errors.extend(_validate_value(name, value, field_schema))
    return errors


def _normalize_for_search(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _quote_appears_in(quote: str | None, markdown: str) -> bool:
    if not quote:
        return False
    return _normalize_for_search(quote) in _normalize_for_search(markdown)


async def extract_page(
    markdown: str,
    schema: dict,
    llm_config: LlmConfig,
    *,
    url: str = "",
    client: httpx.AsyncClient | None = None,
) -> ExtractionResult:
    """Runs the Prompt-to-Extraction pattern (doc1 階段四) against one page's
    Markdown content, returning per-field values with source quotes,
    confidence scores, and independently-verified quote provenance."""
    raw_text = await complete(
        llm_config, _user_prompt(markdown, schema), system=_system_prompt(), client=client
    )
    data = _parse_llm_json(raw_text)
    validation_errors = _validate_against_schema(data, schema)

    fields: dict[str, ExtractedField] = {}
    for name in schema.get("properties", {}):
        entry = data.get(name)
        if not isinstance(entry, dict):
            entry = {}
        source_quote = entry.get("source_quote")
        fields[name] = ExtractedField(
            value=entry.get("value"),
            source_quote=source_quote,
            confidence=entry.get("confidence"),
            quote_verified=_quote_appears_in(source_quote, markdown),
        )

    return ExtractionResult(
        url=url,
        extractor_version=EXTRACTOR_VERSION,
        provider=llm_config.provider,
        model=llm_config.model,
        fields=fields,
        validation_errors=validation_errors,
    )


def _result_to_json(result: ExtractionResult) -> str:
    return json.dumps(
        {
            name: {
                "value": f.value,
                "source_quote": f.source_quote,
                "confidence": f.confidence,
                "quote_verified": f.quote_verified,
            }
            for name, f in result.fields.items()
        },
        ensure_ascii=False,
    )


async def extract_site(
    domain: str,
    schema: dict,
    config: AppConfig,
    llm_config: LlmConfig | None = None,
) -> ExtractionStats:
    """Second pass over already-crawled pages for `domain`: runs
    extract_page() against every stored page that doesn't yet have an
    extraction row for the current EXTRACTOR_VERSION, persisting results."""
    if llm_config is None:
        llm_config = default_config_from_env()

    stats = ExtractionStats()
    store = PageStore(config.storage.db_path)
    try:
        rows = store.pages_without_extraction(domain, EXTRACTOR_VERSION)
        async with httpx.AsyncClient(timeout=60.0) as client:
            for row in rows:
                # pages.markdown_path is unreliable (nulled out on unchanged
                # re-crawls — see store.upsert()), so derive the path the
                # same way write_parsed() constructed it in the first place.
                markdown_path = config.storage.parsed_dir / row["domain"] / f"{row['document_id']}.md"
                if not markdown_path.exists():
                    stats.skipped_missing_markdown += 1
                    logger.warning("no parsed markdown for %s (%s)", row["url"], markdown_path)
                    continue

                markdown = markdown_path.read_text(encoding="utf-8")
                try:
                    result = await extract_page(
                        markdown, schema, llm_config, url=row["url"], client=client
                    )
                except ExtractionError as exc:
                    stats.failed += 1
                    logger.warning("extraction failed for %s: %s", row["url"], exc)
                    continue

                store.save_extraction(
                    ExtractionRecord(
                        document_id=row["document_id"],
                        extractor_version=EXTRACTOR_VERSION,
                        url=row["url"],
                        provider=result.provider,
                        model=result.model,
                        extracted_json=_result_to_json(result),
                        validation_errors=(
                            json.dumps(result.validation_errors, ensure_ascii=False)
                            if result.validation_errors
                            else None
                        ),
                        created_at=_now(),
                    )
                )
                stats.extracted += 1
    finally:
        store.close()
    return stats
