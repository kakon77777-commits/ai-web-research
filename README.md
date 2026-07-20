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

Not in scope yet: LLM-driven browser-agent fallback for JS-heavy interaction
(doc 階段三), near-duplicate detection, and the directory website itself —
those are later phases per the doc's own roadmap.

## Semantic extraction (階段四)

`crawler extract <url> [--schema PATH]` is a second pass over pages already
crawled for that domain: for every page without an extraction row yet, it
sends the page's Markdown plus a caller-supplied JSON Schema to the
configured LLM (Prompt-to-Extraction, doc section 11.2) and asks for
structured values. Deliberately separate from the `crawl` command — this
stage is LLM-rate-limited and independently re-runnable (bump
`EXTRACTOR_VERSION` in `semantic_extract.py` to force a redo with a new
prompt/model without losing prior results).

Every returned field carries a `source_quote` the LLM must copy verbatim
from the page — `semantic_extract.py` independently checks that quote
actually appears in the source text (whitespace/case-insensitive substring
match) before trusting the field, and marks it `quote_verified: false`
otherwise. This is the doc's own 驗證規則 requirement, implemented as a real
deterministic check against its own stated hallucination risk (12.1), not
another LLM call grading its own output. Malformed/wrong-type/off-enum
values are caught by a small hand-rolled JSON Schema subset validator
(`type`, `properties`, `required`, `enum`, `items.type`) — no external
schema-validation dependency.

```bash
# uses config/extraction_schema.example.json by default — copy and edit it
# for a specific extraction task, the extractor itself is schema-agnostic
python -m crawler extract https://example.com/ --verbose

# with a custom schema
python -m crawler extract https://example.com/ --schema path/to/schema.json
```

Results land in the `extractions` table in `storage/metadata/crawl.db`
(`document_id` + `extractor_version` as the primary key), not a new file per
page — query it directly or via `PageStore.get_extraction()`.

## LLM provider (optional, for later semantic-extraction work)

`src/crawler/llm.py` is a minimal provider abstraction across three paths:

- **Anthropic** direct API
- any **OpenAI-compatible** chat-completions endpoint (OpenAI itself, Grok,
  Gemini's OpenAI-compat endpoint, etc.) selected by `base_url` — one code
  path covers all of them since they share the same wire format
- **Google Vertex AI** (Gemini), via the official `google-genai` SDK (an
  optional dependency, `pip install -e ".[vertex]"`) since GCP's
  service-account OAuth2 flow isn't worth reimplementing by hand

The first two mirror the `callAiProvider()` pattern in
[eveglyph-editor](../eveglyph-editor/src/ai.js) — raw `httpx`, no SDK, both
branches symmetric and easy to audit.

Configure via a local `.env` (gitignored, never commit it):

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # optional, this is the default

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini                     # optional, this is the default
OPENAI_BASE_URL=https://api.openai.com/v1    # optional; swap for Grok/Gemini/etc.

VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_CREDENTIALS_PATH=/path/to/service-account-key.json
VERTEX_LOCATION=us-central1                  # optional, this is the default
VERTEX_MODEL=gemini-2.5-flash-lite           # optional, this is the default — cheap tier, no deep reasoning needed here

LLM_PROVIDER=vertex  # optional; picks which configured provider is default — vertex/Gemini by default here since that quota is by far the largest
```

If you're pointing this at a real Vertex AI project, list what your project
can actually call before hardcoding a model name — Model Garden entries can
be listed but not necessarily invokable in every region:

```python
from google import genai
client = genai.Client(vertexai=True, project="...", location="us-central1")
for m in client.models.list():
    if "gemini" in m.name.lower():
        print(m.name)
```

Nothing in the crawl pipeline calls `llm.py` yet — it exists so extraction/
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
