# ai-web-research

A deterministic, no-LLM, reliable site crawler. Milestone toward the layered
crawler architecture described in
`網路爬蟲、AI 爬蟲與 Agent 自動化搜尋技術整理` (2026-07-14): robots.txt + sitemap
discovery, domain-scoped BFS crawling, Crawl4AI-based fetch, raw HTML + Markdown
storage, SHA-256 change detection, a persistent/resumable frontier, per-domain
rate limiting, and SQLite metadata tracking.

This is the base layer that a later phase will use to populate and continuously
update the "通用動態策展目錄" (Universal Dynamic Curated Directory) site.

## What this covers (and doesn't)

Per the source doc's own MVP staging (階段一 + 階段二), extraction stays
deterministic — no LLM calls yet:

- Reads `robots.txt` and honors `Disallow` / `Crawl-delay`.
- Discovers pages via sitemap (`sitemapindex` + `urlset`, recursive) and via
  same-domain `<a href>` links (BFS, bounded by `max_depth` / `max_pages`).
- Fetches pages with Crawl4AI (headless Chromium), with retry + exponential
  backoff on failure.
- Blocks SSRF targets (loopback, private/link-local ranges, cloud metadata IP,
  non-http(s) schemes) before every fetch.
- Extracts title / author / published date / canonical URL / language from
  meta tags, Open Graph, and JSON-LD — no model calls.
- Saves raw HTML + Markdown to `storage/raw/<domain>/` and
  `storage/parsed/<domain>/`, and records metadata (URL, hash, status code,
  timestamps, extracted fields) in `storage/metadata/crawl.db` (SQLite).
- Re-running against the same site only re-saves pages whose content hash
  changed; unchanged pages are marked with `unchanged_since` instead.
- **Persistent, resumable frontier**: every in-scope discovered URL is
  recorded in a `frontier` table (`pending` / `done`) regardless of whether
  the current run's page budget has room for it. A later invocation for the
  same domain picks up `pending` URLs first, and `max_pages_per_domain` is a
  cumulative cap across runs (not reset each invocation). Pass `--fresh` to
  discard persisted frontier state and start a domain over.
- **Per-domain rate limiting**: honors robots.txt `Crawl-delay`, plus a
  configurable `min_request_interval_seconds`, with random jitter so requests
  aren't lockstep-periodic.

Not in scope yet: LLM-driven browser-agent fallback for JS-heavy interaction,
near-duplicate detection, ranking, and the directory website itself — those
are later phases per the doc's own roadmap.

## LLM provider (optional, for later semantic-extraction work)

`src/crawler/llm.py` is a minimal provider abstraction — Anthropic direct, or
any OpenAI-compatible chat-completions endpoint (OpenAI, Grok, Gemini's
OpenAI-compat endpoint, etc.) selected by `base_url` — mirroring the
`callAiProvider()` pattern in
[eveglyph-editor](../eveglyph-editor/src/ai.js). No provider SDKs, just
`httpx`, so both branches stay symmetric and easy to audit.

Configure via a local `.env` (gitignored, never commit it):

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # optional, this is the default

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini                     # optional, this is the default
OPENAI_BASE_URL=https://api.openai.com/v1    # optional; swap for Grok/Gemini/etc.

LLM_PROVIDER=anthropic  # optional; picks which configured provider is default
```

Nothing in the crawl pipeline calls this yet — it exists so extraction/
browser-agent stages can be wired in against a cheap model without picking a
single vendor up front.

## Setup

```bash
uv venv
uv pip install -e .
.venv/Scripts/python.exe -m playwright install chromium
```

## Usage

```bash
python -m crawler crawl https://example.com/ --max-pages 50 --max-depth 3 --verbose

# Force a full re-crawl instead of resuming from persisted frontier state:
python -m crawler crawl https://example.com/ --max-pages 50 --fresh
```

Config defaults live in `config/crawler.yaml` (user agent, concurrency,
timeouts, retry/backoff, rate limiting, SSRF policy). CLI flags `--max-pages` /
`--max-depth` override the config for a single run.

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Unit tests use `httpx.MockTransport` / fixtures — no live network calls.
