# Fetched-Page Source Signals v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive auditable reverse-source signals and explicit source-family relations from already-fetched page content, then feed them into the existing AI Daily live-discovery pipeline without fixture-supplied lineage.

**Architecture:** Add a bounded `FetchedPage` bridge, a deterministic stdlib HTML/JSON-LD signal extractor, and a separate signal compiler under `source_graph/`. Preserve existing reverse-trace and source-family logic; add a new AI Daily wrapper that consumes fetched pages and calls the existing canonical/projection path. No legacy crawler behavior changes and no fuzzy/LLM provenance inference.

**Tech Stack:** Python >=3.11, stdlib `html.parser`, `json`, `urllib.parse`, existing AUSI `ArtifactRef` / `AcquiredAsset` / source-graph / AI Daily contracts, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-fetched-page-source-signals-design.md`

## Global Constraints

- Base on `master@21789cafd527d89ebefc16dc2c9088e7f23afa10`.
- Do not modify `src/crawler/*` behavior.
- Do not modify Patent-domain behavior.
- Do not add runtime dependencies.
- `SearchResult != Evidence`.
- `MentionCount != IndependentEvidenceCount`.
- Generic hyperlinks never create source relations.
- Search rank never creates provenance.
- Citation does not imply source-family collapse.
- Only explicit canonical/syndication/original-source/based-on markers may directly create collapsing relations.
- Linked textual attribution is trace-only in v0.1.
- Missing/ambiguous predecessor remains unresolved.
- No fuzzy text-similarity dependency inference.
- No LLM source-lineage inference.
- Maximum parsed HTML is `1_000_000` characters.
- Maximum emitted signals per page is `128`.
- Extracted quote length is `12..240` normalized characters.
- Default tests are deterministic and network-free.

---

### Task 1: FetchedPage bridge from existing acquisition objects

**Files:**
- Create: `src/ai_web_research/source_graph/fetched_page.py`
- Create: `tests/ausi/test_fetched_page_bridge.py`

**Interfaces:**
- Consumes: `ArtifactRef`, `ArtifactKind.DOCUMENT`, `AcquiredAsset`, injectable `Callable[[str], str]` reader.
- Produces: `FetchedPage`, `FetchedPageError`, `fetched_page_from_document`, `fetched_page_from_asset`.

- [ ] **Step 1: Write failing tests.** Cover a DOCUMENT artifact with `url`, `canonical_url`, `raw_path`, `content_hash`, `fetched_at`, `published_at`, `title`, `author`; assert the injected reader is called with `raw_path` and no network call exists. Cover `AcquiredAsset.raw_ref`, fallback to artifact `raw_path`, missing URL/content ref fail-closed, and deterministic 1,000,000-character truncation with `truncated=True`.
- [ ] **Step 2: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_fetched_page_bridge.py -q`; expect RED because `source_graph.fetched_page` does not exist.
- [ ] **Step 3: Implement immutable model.** Use:

```python
@dataclass(frozen=True)
class FetchedPage:
    source_id: str
    url: str
    canonical_url: str | None
    html: str
    observed_at: str
    published_at: str | None
    content_hash: str | None
    title: str | None
    author: str | None
    content_ref: str
    truncated: bool
```

Generate `source_id` as `source:<normalized-url>` unless an explicit source ID is supplied in metadata.
- [ ] **Step 4: Implement bridges.** `fetched_page_from_document(document, reader, *, max_chars=1_000_000)` requires `document.kind == ArtifactKind.DOCUMENT`, gets content ref from `raw_path` then `markdown_path`, and uses `fetched_at` as observed time. `fetched_page_from_asset(asset, reader, *, max_chars=1_000_000)` prefers `asset.raw_ref`, then delegates artifact metadata. Neither helper refetches URLs.
- [ ] **Step 5: Run** targeted tests and expect PASS.
- [ ] **Step 6: Commit** `feat: add bounded fetched-page bridge`.

### Task 2: Typed HTML and JSON-LD source-signal extraction

**Files:**
- Create: `src/ai_web_research/source_graph/page_signals.py`
- Create: `src/ai_web_research/source_graph/html_extract.py`
- Create: `tests/ausi/test_page_source_signal_extraction.py`

**Interfaces:**
- Consumes: `FetchedPage`.
- Produces: `PageSourceSignalKind`, `PageSourceSignal`, `PageSignalExtraction`, `extract_page_source_signals`.

- [ ] **Step 1: Write failing extraction tests.** Use inline HTML covering: self `<link rel=canonical>`, differing canonical URL, `rel=syndication-source`, `rel=original-source`, `<blockquote cite>`, `<q cite>`, bounded quote text, `og:site_name`, JSON-LD `publisher.name`, `citation`, `isBasedOn`, malformed JSON-LD, unrelated links, and 130 otherwise-valid signals to prove the 128-signal cap.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement signal contracts.** Exact enum values:

```python
CANONICAL_URL
SYNDICATION_SOURCE
ORIGINAL_SOURCE
BASED_ON
CITATION_URL
ATTRIBUTED_URL
ATTRIBUTION_ENTITY
QUOTED_PHRASE
OWNER_HINT
```

`PageSourceSignal` fields: `signal_id`, `source_id`, `kind`, `value`, `locator`, `confidence`, `explicit`. `PageSignalExtraction` fields: `source_id`, `signals`, `warnings`, `truncated`, `parser_version`.
- [ ] **Step 4: Implement bounded stdlib parser.** Subclass `HTMLParser`; inspect `<link>`, `<meta>`, `<blockquote>`, `<q>`, `<a>`, and `script[type=application/ld+json]`. Normalize whitespace, resolve relative URLs with `urljoin(page.url, value)`, and generate deterministic signal IDs from `(source_id, kind, normalized value, locator)`.
- [ ] **Step 5: Implement structural rules.** `canonical`, `syndication-source`, `original-source`, `cite` attributes, `og:site_name`, and JSON-LD fields emit typed signals. JSON-LD traversal is limited to 2,048 dict/list nodes; malformed JSON adds `malformed_json_ld` warning and continues.
- [ ] **Step 6: Implement quotes.** Emit normalized `<blockquote>/<q>` text only when length is 12..240; longer text is clipped to 240 only when a complete normalized prefix remains, with locator indicating tag occurrence.
- [ ] **Step 7: Run** targeted tests and expect PASS.
- [ ] **Step 8: Commit** `feat: extract typed source signals from fetched pages`.

### Task 3: High-precision linked attribution extraction

**Files:**
- Modify: `src/ai_web_research/source_graph/html_extract.py`
- Test: `tests/ausi/test_page_source_signal_extraction.py`

**Interfaces:**
- Produces additional `ATTRIBUTED_URL` / `ATTRIBUTION_ENTITY` signals without direct source-family relations.

- [ ] **Step 1: Add failing tests.** Verify anchors immediately preceded in the same text block by normalized markers `according to`, `via`, or `source:` emit an `ATTRIBUTED_URL`; anchor text emits `ATTRIBUTION_ENTITY` when 2..120 chars. Verify a generic anchor, `read more`, navigation link, and marker more than 80 normalized characters away emit no attribution signal.
- [ ] **Step 2: Run** the specific tests and verify RED.
- [ ] **Step 3: Implement bounded context tracking.** Keep only the last 80 normalized text characters in the active block; reset context at block boundaries (`p`, `li`, `div`, `section`, `article`, headings). At anchor start, record whether the preceding context ends with an approved attribution marker. Emit attribution signals at anchor close using the resolved href and normalized anchor text.
- [ ] **Step 4: Run** extraction suite and expect PASS.
- [ ] **Step 5: Commit** `feat: extract explicit linked attribution signals`.

### Task 4: Compile page signals into trace signals and explicit relations

**Files:**
- Create: `src/ai_web_research/source_graph/signal_compile.py`
- Modify: `src/ai_web_research/source_graph/__init__.py`
- Create: `tests/ausi/test_page_source_relation_compile.py`

**Interfaces:**
- Consumes: `FetchedPage`, `PageSignalExtraction`, existing `SourceTraceSignals`, `SourceRelation`, `SourceRelationType`.
- Produces: `CompiledPageSourceSignals`, `compile_page_source_signals`.

- [ ] **Step 1: Write failing compiler tests.** Verify: self canonical → no relation; differing canonical → explicit `MIRRORS`; syndication → explicit `SYNDICATED_FROM`; original/based-on → explicit `DERIVED_FROM`; citation → explicit `CITES`; linked textual attribution → trace URL/entity only and no relation; quote → `quoted_phrases`; owner hint → attribution entity/metadata only; duplicate normalized values fold deterministically.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement result model.** Fields:

```python
@dataclass(frozen=True)
class CompiledPageSourceSignals:
    source_id: str
    trace_signals: SourceTraceSignals
    relations: tuple[SourceRelation, ...]
    owner_hints: tuple[str, ...]
    signal_ids: tuple[str, ...]
```

- [ ] **Step 4: Implement relation mapping.** Strong structural signals create explicit confidence `1.0` relations. Target source IDs use `source:<normalized-url>`. Relation IDs hash `(from, relation_type, to, signal_id)`. `CITES` is non-collapsing because existing family resolver already excludes it.
- [ ] **Step 5: Implement trace mapping.** `SYNDICATION_SOURCE`, `ORIGINAL_SOURCE`, `BASED_ON`, `CITATION_URL`, and `ATTRIBUTED_URL` contribute URLs; `ATTRIBUTION_ENTITY` contributes entities; `QUOTED_PHRASE` contributes quote searches. Canonical URL is excluded from reverse-trace URL actions because its semantics are already materialized structurally.
- [ ] **Step 6: Run** targeted tests plus existing `test_reverse_source_trace.py` and `test_source_family.py`; expect PASS.
- [ ] **Step 7: Commit** `feat: compile page signals into source lineage`.

### Task 5: AI Daily wrapper that derives lineage from fetched pages

**Files:**
- Modify: `src/ai_web_research/domains/ai_industry/live_discovery.py`
- Create: `tests/ausi/fixtures/ai_daily_fetched_source_scenario.py`
- Create: `tests/ausi/test_ai_daily_fetched_source_e2e.py`

**Interfaces:**
- Consumes: existing `build_ai_daily_from_discovery`, `FetchedPage`, extractor/compiler outputs.
- Produces: `FetchedSourcePageResult`, `AIDailyFetchedSourceResult`, `build_ai_daily_from_fetched_pages`.

- [ ] **Step 1: Write failing E2E fixture/test.** Four HTML pages: Official Blog self-canonical; Official Repo self-canonical; Media A has explicit `rel=original-source` to Official Blog and a quote; Media B has explicit `rel=syndication-source` to Media A. Synthetic Brave discovery observation contains all four URLs. Do not provide `SourceTraceSignals` or collapsing `base_relations` in the fixture.
- [ ] **Step 2: Assert extraction.** Media A produces `ORIGINAL_SOURCE` + quote; Media B produces `SYNDICATION_SOURCE`; official pages create no predecessor dependency.
- [ ] **Step 3: Assert family semantics.** Compiled relations resolve Media B → Media A → Official Blog into one family while Official Repo remains a second family; `independent_root_count == 2`.
- [ ] **Step 4: Assert canonical projection.** Release claim receives runtime-computed count 2, event remains confirmed, machine + zh-Hant artifacts share one KnowledgeStateID, and search snippets/page source signals do not appear in `evidence_ids`.
- [ ] **Step 5: Run** E2E and verify RED before wrapper exists.
- [ ] **Step 6: Implement wrapper.** Extract/compile each page, build a deterministic `trace_signals_by_source` map and relation tuple, then call existing `build_ai_daily_from_discovery()` with `base_relations=compiled_relations`. To avoid double materialization, pass trace signals with structural dependency URLs removed after compiler materializes them; preserve quote/entity/trace-only attribution actions.
- [ ] **Step 7: Return extraction audit.** `AIDailyFetchedSourceResult` contains the underlying `AIDailyDiscoveryResult` plus per-source extraction/compiler results for audit.
- [ ] **Step 8: Run** targeted E2E and all PR #3 AI Daily/source-lineage tests; expect PASS.
- [ ] **Step 9: Commit** `feat: derive AI Daily source lineage from fetched pages`.

### Task 6: Documentation, fresh verification, delivery, and PR

**Files:**
- Create: `docs/AI_DAILY_FETCHED_SOURCE_SIGNALS_v0.1.md`

**Interfaces:**
- Produces reviewer-ready branch and PR against `master`.

- [ ] **Step 1: Document extraction boundary.** State exact structural markers, attribution markers, parser bounds, no fuzzy/LLM inference, and that page-source signals are provenance metadata—not canonical evidence.
- [ ] **Step 2: Document FS-01..FS-10** with exact tests and expected semantics.
- [ ] **Step 3: Fresh verification.** Run all locally available `tests/ausi` from the reconstructed/full checkout, plus `compileall`. Report exact count; do not reuse historical PR counts as fresh evidence.
- [ ] **Step 4: Run full legacy tests only if a complete checkout is actually available.** If unavailable, disclose the limitation exactly; never infer legacy success from AUSI success.
- [ ] **Step 5: Compare** `master...integration/fetched-page-source-signals-v0.1`; verify `behind 0`, no `src/crawler/*` changes, no Patent-domain changes.
- [ ] **Step 6: Create a delivery ZIP** containing the new source, tests, fixture, reviewer doc, sample extraction JSON, sample machine/zh-Hant output, `VALIDATION.json`, and SHA256 checksums.
- [ ] **Step 7: Open PR** against `master` titled `feat: derive source lineage from fetched pages v0.1` with exact verification evidence, limitations, and next slice: execute quote/entity trace actions through the provider-neutral orchestrator, then confidence-scored predecessor heuristics / B04 historical modes.
