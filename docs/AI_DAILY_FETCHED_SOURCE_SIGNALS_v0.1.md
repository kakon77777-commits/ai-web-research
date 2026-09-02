# AI Daily Fetched-Page Source Signals v0.1

**Date:** 2026-09-01  
**Base:** `master@21789cafd527d89ebefc16dc2c9088e7f23afa10`  
**Branch:** `integration/fetched-page-source-signals-v0.1`

## Purpose

This slice removes fixture-supplied source-lineage signals from the AI Daily E2E path.

```text
Search candidates
→ fetched/acquired page
→ bounded FetchedPage
→ typed PageSourceSignal extraction
→ typed source relations + reverse-trace signals
→ SourceFamilyResolution
→ runtime independent-root count
→ existing CanonicalClaim / CanonicalEvent
→ existing Daily Batch / machine + zh-Hant projection
```

## Acquisition boundary

The implementation does **not** modify `src/crawler/*` and does not refetch URLs. `FetchedPage` is materialized from existing `DOCUMENT` `ArtifactRef` or `AcquiredAsset` data using an injected text reader.

Content references are selected in this order:

```text
AcquiredAsset.raw_ref
→ ArtifactRef.metadata.raw_path
→ ArtifactRef.metadata.markdown_path
```

Maximum parsed content is 1,000,000 characters. Oversized input is deterministically truncated and marked.

## Signal layer

Typed page signal kinds:

```text
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

Each signal stores a deterministic ID, source ID, normalized value, locator, confidence, and explicit/inferred classification.

## Structural markers

High-precision structural extraction supports:

```html
<link rel="canonical" href="...">
<link rel="syndication-source" href="...">
<link rel="original-source" href="...">
<blockquote cite="...">...</blockquote>
<q cite="...">...</q>
<meta property="og:site_name" content="...">
```

JSON-LD extraction supports URL-valued:

```text
citation
isBasedOn
isBasedOnUrl
syndicationSource
publisher.name
```

Malformed JSON-LD fails soft with a warning. JSON-LD traversal is bounded to 2,048 dict/list nodes. Page signals are capped at 128 per page.

## Linked textual attribution

The parser recognizes only bounded, high-precision linked attribution:

```text
According to <a href="...">Source</a>
via <a href="...">Source</a>
source: <a href="...">Source</a>
```

Rules:

- attribution marker must be in the same text block;
- marker must be within the last 80 normalized characters before the anchor;
- `nav`, `header`, `footer`, and `aside` are excluded;
- generic links, read-more links, related links, and distant markers produce no attribution signal.

These textual attributions are **trace-only**. They do not directly collapse source families.

## Relation compiler

Typed relation mapping:

| Signal | Relation | Collapses family? |
|---|---|---:|
| differing canonical | `MIRRORS` | yes |
| syndication source | `SYNDICATED_FROM` | yes |
| original source | `DERIVED_FROM` | yes |
| based-on source | `DERIVED_FROM` | yes |
| citation URL | `CITES` | no |
| linked textual attribution | none | no |
| quoted phrase | none | no |
| owner hint | none | no |

Self-canonical URLs create no relation.

`CITES` is preserved as a non-collapsing trace relation. Search rank is never used to create provenance.

## Compatibility with PR #3

`build_ai_daily_from_discovery()` retains its prior behavior by default:

```python
materialize_trace_edges=True
```

The new `build_ai_daily_from_fetched_pages()` wrapper calls it with:

```python
materialize_trace_edges=False
```

because the typed compiler is authoritative for relation type in the fetched-page path. This prevents a citation or textual attribution URL from being incorrectly re-materialized by the older URL-match path as `DERIVED_FROM`.

## E2E pressure fixture

Four fetched pages:

```text
Official Blog        self canonical
Official Repository  self canonical
Media A              original-source → Official Blog + quote
Media B              syndication-source → Media A
```

Automatically derived lineage:

```text
Media B --SYNDICATED_FROM--> Media A --DERIVED_FROM--> Official Blog
Official Repository ---------------------------------------> independent root
```

Result:

```text
raw mentioned sources = 4
independent source families = 2
canonical claim independent_root_count = 2
```

The fixture does not supply `SourceTraceSignals` and does not supply collapsing `base_relations`.

## Acceptance criteria

- [x] **FS-01** `DOCUMENT` / `AcquiredAsset` materialize bounded local `FetchedPage`; no refetch.
- [x] **FS-02** canonical URL extracted; self-canonical does not create false dependency.
- [x] **FS-03** explicit syndication marker → `SYNDICATED_FROM`.
- [x] **FS-04** original / based-on marker → `DERIVED_FROM`.
- [x] **FS-05** explicit citation → `CITES`, non-collapsing.
- [x] **FS-06** bounded quote → exact-quote trace signal with locator.
- [x] **FS-07** linked `according to` / `via` / `source:` → trace signal only.
- [x] **FS-08** owner/publisher hints remain metadata only.
- [x] **FS-09** generic unrelated links produce no source relation.
- [x] **FS-10** fetched-page E2E derives `4 mentions → 2 source families → independent_root_count=2` and preserves machine/zh-Hant projection semantics.

## Fresh verification in this environment

The locally materialized AI Daily / discovery / source-graph stack plus this slice was verified with:

```text
58 passed in 0.14s
compileall exit 0
```

The 58 fresh tests cover:

- canonical knowledge store;
- AI claim/event canonicalization;
- bounded Daily selection;
- machine + zh-Hant projection;
- AI Daily canonical E2E;
- discovery normalization;
- source-family resolution;
- reverse-source trace planning;
- runtime source-independence attachment;
- PR #3 live-discovery E2E;
- fetched-page bridge;
- page source-signal extraction;
- page signal compiler;
- fetched-page AI Daily E2E.

## Verification limitation

This sandbox still does not have a complete local checkout of all PR #1 AUSI/provider/Patent/legacy packages. The local reconstruction therefore cannot freshly collect every repository test. In particular, the historical Brave provider contract tests depend on `methods/providers/policy` packages not present in the reconstructed checkout.

This document does **not** relabel prior PR test counts as fresh results. GitHub branch comparison and repository CI status are reported separately at PR closure.

## Explicit non-goals

No v0.1 implementation for:

- fuzzy text-copy detection;
- semantic predecessor inference;
- OCR / image source tracing;
- LLM provenance inference;
- automatic execution of quote/entity reverse-search actions;
- B04 `PUBLIC_AS_AVAILABLE` backfill.

## Next slice

Execute generated `EXACT_QUOTE_SEARCH` and `ENTITY_SEARCH` actions through the provider-neutral orchestrator, then add confidence-scored predecessor heuristics that remain separated from explicit provenance. After that, extend B04 historical reconstruction / backfill modes.
