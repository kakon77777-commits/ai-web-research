# ai-web-research

Stage 1 AI crawler — a deterministic, no-LLM, reliable single-site crawler. First
milestone toward the layered crawler architecture described in
`網路爬蟲、AI 爬蟲與 Agent 自動化搜尋技術整理` (2026-07-14): robots.txt + sitemap
discovery, domain-scoped BFS crawling, Crawl4AI-based fetch, raw HTML + Markdown
storage, SHA-256 change detection, and SQLite metadata tracking.

This is the base layer that a later phase will use to populate and continuously
update the "通用動態策展目錄" (Universal Dynamic Curated Directory) site.

## What this stage does (and doesn't)

Per the source doc's own MVP staging, stage 1 is deliberately deterministic —
no LLM extraction yet:

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

Not in scope yet: LLM/semantic extraction, browser-agent fallback for
JS-heavy interaction, near-duplicate detection, ranking, and the directory
website itself — those are later phases per the doc's own roadmap.

## Setup

```bash
uv venv
uv pip install -e .
.venv/Scripts/python.exe -m playwright install chromium
```

## Usage

```bash
python -m crawler crawl https://example.com/ --max-pages 50 --max-depth 3 --verbose
```

Config defaults live in `config/crawler.yaml` (user agent, concurrency,
timeouts, retry/backoff, SSRF policy). CLI flags `--max-pages` / `--max-depth`
override the config for a single run.

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Unit tests use `httpx.MockTransport` / fixtures — no live network calls.
