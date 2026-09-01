# Fetched-Page Source Signals v0.1 — Design Specification

**Date:** 2026-09-01  
**Repository:** `kakon77777-commits/ai-web-research`  
**Base:** `master@21789cafd527d89ebefc16dc2c9088e7f23afa10`  
**Target branch:** `integration/fetched-page-source-signals-v0.1`

## 1. Goal

Replace fixture-supplied `SourceTraceSignals` / source-dependency relations in the AI Daily live-discovery MVP with deterministic, auditable extraction from already-acquired page content.

Target path:

```text
Search
→ Fetch / Acquired Page
→ FetchedPage
→ PageSourceSignal extraction
→ SourceTraceSignals + explicit SourceRelation compilation
→ existing Reverse Trace / SourceFamilyResolution
→ existing CanonicalClaim / CanonicalEvent
→ existing Daily Batch / zh-Hant + machine projection
```

This slice does **not** modify legacy `src/crawler/*` behavior. `LegacyFetchAdapter` already returns a `DOCUMENT` artifact with URL, canonical URL, raw/markdown paths, hashes, and timestamps. The new code consumes that output.

## 2. Design choice

Three approaches were considered:

1. Parse HTML directly into `SourceTraceSignals`. Fast, but loses why a signal was recognized.
2. **Chosen:** parse HTML into typed `PageSourceSignal` objects with locator, kind, confidence, and target; then compile those signals into trace actions and explicit source relations.
3. Use an LLM to infer source lineage from full text. Flexible but expensive and risks mixing semantic guessing with provenance.

v0.1 chooses option 2. The typed intermediate layer preserves the evidence for a provenance decision and keeps extraction separate from lineage interpretation.

## 3. Hard invariants

- `SearchResult != Evidence`.
- `MentionCount != IndependentEvidenceCount`.
- Search rank never creates provenance.
- Generic hyperlinks never create source relations.
- Citation does not imply dependency-family collapse.
- Only strong explicit dependency markers may directly create collapsing relations.
- Missing/ambiguous predecessor remains unresolved; never fabricate one.
- No fuzzy copy/similarity inference in v0.1.
- No LLM source-lineage inference in v0.1.
- No new runtime dependency.
- No changes to legacy `src/crawler/*` behavior.
- No changes to Patent-domain behavior.

## 4. FetchedPage bridge

Add a focused immutable `FetchedPage` representation:

```python
@dataclass(frozen=True)
class FetchedPage:
    source_id: str
    url: str
    canonical_url: str | None
    html: str
    observed_at: str
    published_at: str | None = None
    content_hash: str | None = None
    title: str | None = None
    author: str | None = None
```

Bridge helpers accept either a `DOCUMENT` `ArtifactRef` or an `AcquiredAsset` plus an injectable text reader. The bridge uses `raw_ref` / `raw_path` first when present and fails closed if there is no readable fetched content. It never refetches the web.

Resource bounds:

- maximum HTML characters: `1_000_000`;
- oversized input is truncated deterministically and marked in extraction metadata;
- no script execution;
- no OCR.

## 5. Typed page signals

Add:

```python
class PageSourceSignalKind(StrEnum):
    CANONICAL_URL = "canonical_url"
    SYNDICATION_SOURCE = "syndication_source"
    ORIGINAL_SOURCE = "original_source"
    BASED_ON = "based_on"
    CITATION_URL = "citation_url"
    ATTRIBUTED_URL = "attributed_url"
    ATTRIBUTION_ENTITY = "attribution_entity"
    QUOTED_PHRASE = "quoted_phrase"
    OWNER_HINT = "owner_hint"

@dataclass(frozen=True)
class PageSourceSignal:
    signal_id: str
    source_id: str
    kind: PageSourceSignalKind
    value: str
    locator: str
    confidence: float
    explicit: bool
```

Extraction returns a `PageSignalExtraction` containing signals, warnings, truncation status, and parser version.

Signal IDs are content-sensitive and deterministic.

## 6. High-precision extraction rules

### 6.1 Canonical link

Extract:

```html
<link rel="canonical" href="...">
```

A self-canonical URL is metadata only and creates no relation. A differing canonical URL may compile to `MIRRORS` only when the marker is explicit and URL-normalized.

### 6.2 Syndication source

Extract explicit structural markers such as:

```html
<link rel="syndication-source" href="...">
```

or structured JSON-LD fields explicitly named `syndicationSource` when they contain a URL.

Compile to:

```text
SYNDICATED_FROM
confidence = 1.0
inference_type = EXPLICIT
```

This relation participates in source-family collapse.

### 6.3 Original / based-on source

Extract explicit structural markers:

- `rel="original-source"`;
- JSON-LD `isBasedOn`, `isBasedOnUrl`, or URL-valued equivalent supported by the parser.

Compile to `DERIVED_FROM`, explicit confidence 1.0. This relation participates in family collapse.

### 6.4 Citation

Extract:

- `<blockquote cite="...">`;
- `<q cite="...">`;
- JSON-LD `citation` URL;
- clearly labeled citation links where markup explicitly expresses citation semantics.

Compile to `CITES`, explicit. `CITES` does **not** collapse source families.

### 6.5 Linked textual attribution

Recognize only bounded high-precision text patterns around an anchor, e.g.:

```text
according to <a href="...">Organization X</a>
via <a href="...">Source Y</a>
source: <a href="...">Source Y</a>
```

Emit `ATTRIBUTED_URL` + optionally `ATTRIBUTION_ENTITY`. This is a trace signal only in v0.1. It must not directly compile to a collapsing `DERIVED_FROM` relation.

### 6.6 Quoted phrase

Extract bounded text from `<blockquote>` / `<q>` as `QUOTED_PHRASE` when normalized length is 12–240 characters. This can generate an exact-quote reverse-search action. The quote itself is not provenance.

### 6.7 Owner / publisher hint

Extract metadata from explicit author/publisher/site-name fields such as JSON-LD `publisher.name` and common `og:site_name` metadata. This is metadata only, never a source dependency relation.

## 7. JSON-LD handling

Use stdlib `json` only. Parse `<script type="application/ld+json">` payloads with these restrictions:

- no JavaScript execution;
- malformed JSON fails soft and adds a warning;
- recursively inspect dict/list values only up to a bounded node count;
- accept URL values only for explicit source/citation fields;
- do not infer relationships from generic `sameAs` in this slice.

## 8. Signal compiler

Add a compiler that produces two outputs:

1. `SourceTraceSignals` for the existing reverse-trace planner;
2. explicit `SourceRelation` objects for relation types whose semantics are strong enough to materialize immediately.

Mapping:

| Signal | Trace signal | Direct relation | Family collapse |
|---|---|---|---|
| self canonical | no | none | no |
| differing canonical | URL metadata | `MIRRORS` | yes |
| syndication source | attributed URL | `SYNDICATED_FROM` | yes |
| original / based-on | attributed URL | `DERIVED_FROM` | yes |
| citation URL | attributed URL | `CITES` | no |
| linked textual attribution | attributed URL/entity | none | no |
| quote | quoted phrase | none | no |
| owner hint | entity hint only | none | no |

The compiler deduplicates by `(kind, normalized value)` while retaining deterministic signal order.

## 9. AI Daily integration

Preserve `build_ai_daily_from_discovery()` for compatibility. Add a new thin wrapper, e.g.:

```python
build_ai_daily_from_fetched_pages(...)
```

It accepts:

- provider observation;
- fetched pages or acquired assets;
- source nodes;
- already verified evidence IDs / claim draft;
- event draft and existing projection inputs.

For each fetched page it:

1. extracts typed page signals;
2. compiles trace signals + explicit relations;
3. feeds trace signals to existing planner;
4. combines compiled explicit relations with any independently verified relations;
5. resolves source families;
6. computes independent-root count;
7. calls the existing canonical/publishing path.

The wrapper does not turn page text or search snippets into evidence. Claim evidence remains supplied by the trusted evidence layer.

## 10. End-to-end fixture

Use four fetched HTML pages:

- **Official Blog** — self canonical, no predecessor.
- **Official Repository** — self canonical, no predecessor.
- **Media A** — explicit `original-source`/`isBasedOn` to Official Blog and a quoted phrase.
- **Media B** — explicit `syndication-source` to Media A.

The fixture also supplies a synthetic Brave discovery observation for the same URLs and existing trusted evidence IDs.

Expected lineage:

```text
Media B --SYNDICATED_FROM--> Media A --DERIVED_FROM--> Official Blog
Official Repository ---------------------------------------> independent root
```

Expected:

```text
raw mentioned sources = 4
independent source families = 2
canonical claim independent_root_count = 2
```

No fixture-supplied `SourceTraceSignals` and no fixture-supplied collapsing base relation are allowed in this E2E.

## 11. Acceptance criteria

- **FS-01** `DOCUMENT` / `AcquiredAsset` can materialize a bounded `FetchedPage` using an injected reader; no web refetch and no crawler mutation.
- **FS-02** canonical URL is extracted and self-canonical does not create a false dependency.
- **FS-03** explicit syndication source compiles to `SYNDICATED_FROM`.
- **FS-04** explicit original / based-on source compiles to `DERIVED_FROM`.
- **FS-05** explicit citation compiles to `CITES` and does not collapse source families.
- **FS-06** bounded quote text produces an exact-quote trace signal with locator.
- **FS-07** linked `according to` / `via` attribution produces trace actions but no collapsing relation.
- **FS-08** owner/publisher hints are metadata only.
- **FS-09** unrelated generic links produce no source signal/relation.
- **FS-10** fetched-page E2E automatically yields `4 mentions → 2 source families → independent_root_count=2` and preserves existing machine/zh-Hant projection semantics.

## 12. Non-goals / next slices

Not included in v0.1:

- fuzzy phrase overlap / plagiarism detection;
- similarity-based `derived_from` inference;
- OCR/image source tracing;
- archive/Memento temporal reconstruction;
- automatic execution of quote/entity trace actions through the full orchestrator;
- confidence learning from historical source behavior.

After this slice, the next logical step is provider-neutral execution of generated reverse-trace actions, followed by confidence-scored predecessor heuristics and then B04 `PUBLIC_AS_AVAILABLE` / backfill semantics.
