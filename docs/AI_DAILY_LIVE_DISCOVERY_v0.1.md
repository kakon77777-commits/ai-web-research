# AI Daily Live Discovery + Source Lineage v0.1

**Status:** Implemented / stacked on AI Daily canonical MVP v0.1  
**Date:** 2026-08-31  
**Base:** `integration/ai-daily-mvp-v0.1`  
**Head:** `integration/ai-daily-live-discovery-v0.1`

## Purpose

This slice replaces the AI Daily MVP's fixture-supplied source-independence count with runtime discovery and source-family resolution:

```text
Query
→ Brave Search candidate observation
→ provider-neutral DiscoveryCandidate
→ reverse-source trace plan
→ explicit source dependency relations
→ source-family collapse
→ independent-root count
→ existing CanonicalClaim / CanonicalEvent
→ existing DailyBatch / machine JSON / zh-Hant projection
```

## Brave provider boundary

The first general search backend is Brave Search API:

```text
provider.brave_search@1.0.0
surface.brave_search.web
brave_search.web@1.0.0
binding.lexical_search.brave_search.v1
```

Endpoint:

```text
GET https://api.search.brave.com/res/v1/web/search
```

Authentication is execution-time only:

```text
ExecutionContext.services["brave_search_api_key"]
→ X-Subscription-Token
```

The credential is not stored in ProviderSpec, MethodBinding, ProviderObservation, DiscoveryCandidate, evidence, receipts, or documentation.

No Brave credential is present in the current sandbox. The optional live smoke therefore correctly returns:

```text
SKIPPED_NO_CREDENTIAL
```

This document does **not** claim an authenticated live Brave request.

## Discovery is not evidence

Brave web results are normalized as `ArtifactKind.CANDIDATE` and then `DiscoveryCandidate` with:

```text
evidence_role = discovery_only
source_type = brave_web_search_result
```

Search title/snippet/rank are discovery metadata. They are never promoted to `CandidateEvidence` by this slice.

## Source-family semantics

Collapsing dependency relations:

```text
syndicated_from
mirrors
derived_from
translated_from
same_origin_family
```

Non-collapsing trace relations:

```text
cites
links_to
mentions
```

The resolver uses deterministic family IDs and preserves unresolved cyclic families with `root_resolved=false` rather than inventing a provenance root.

`independent_root_count(source_ids)` counts unique resolved/unresolved source families, not raw mentions.

## Reverse trace semantics

Provider-neutral actions:

```text
DIRECT_PREDECESSOR
EXACT_QUOTE_SEARCH
ENTITY_SEARCH
```

Only an explicit attributed URL exactly matching a returned discovery candidate creates a dependency edge in v0.1. Quote/entity search hits remain candidates until separately verified. Provider rank alone never creates a dependency edge.

## E2E pressure-test fixture

Synthetic Brave observation:

```text
official blog
official repository
Media A
Media B
```

Source lineage:

```text
Media B --syndicated_from--> Media A --explicit_attribution--> Official Blog
Official Repository ---------------------------------------> independent root
```

Result:

```text
raw source mentions = 4
independent source families = 2
canonical claim independent_root_count = 2
```

The existing AI Daily projection remains unchanged:

```text
[已確認] Model X 已正式發布。
```

Machine and zh-Hant artifacts share one `KnowledgeStateID`.

## Acceptance criteria

- [x] LD-01 Brave adapter requires runtime credential and does not serialize it.
- [x] LD-02 Brave outputs are explicitly `discovery_only` candidates.
- [x] LD-03 URL/title/rank normalization is deterministic and duplicate URLs fold.
- [x] LD-04 explicit syndicated/mirror/derived/translated/same-origin relations collapse into source families.
- [x] LD-05 independent-root count is computed from runtime family resolution.
- [x] LD-06 quote/entity reverse-trace actions are provider-neutral.
- [x] LD-07 no trace signal yields explicit unresolved origin.
- [x] LD-08 provider rank alone creates no source-dependency edge.
- [x] LD-09 AI release claim receives runtime-computed `independent_root_count=2`.
- [x] LD-10 existing machine + zh-Hant projection state/status semantics remain unchanged.

## Fresh verification

Executed on the locally reconstructed PR #2 + current live-discovery slice:

```text
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi -q
45 passed in 0.72s

PYTHONPATH=src python -m compileall -q \
  src/ai_web_research tests/ausi scripts/verify_brave_search_provider.py
exit 0

env -u BRAVE_SEARCH_API_KEY PYTHONPATH=src \
  python scripts/verify_brave_search_provider.py
SKIPPED_NO_CREDENTIAL
```

The 45 tests comprise the previously implemented AI Daily canonical slice plus the current Brave/discovery/source-lineage tests available in the reconstructed checkout.

## Verification limitation

The sandbox still cannot clone the complete GitHub repository through normal outbound Git/DNS access. Therefore this slice does **not** claim a fresh run of every pre-existing PR #1 AUSI/Patent test or legacy `src/crawler` test.

PR #1 separately reports its own earlier AUSI baseline; that prior result is not relabeled as a fresh result here.

GitHub compare against `integration/ai-daily-mvp-v0.1` at closure showed:

```text
status = ahead
ahead_by = 8
behind_by = 0
```

Before this documentation commit, all 21 changed files were additions. No `src/crawler/*` or `src/ai_web_research/domains/patents/*` file was changed.

## Next slice

The next useful increment is no longer another search provider. It is **fetched-page source-signal extraction**: automatically derive attributed URLs, quote signals, source ownership hints, and syndication indicators from acquired snapshots, so `SourceTraceSignals` and base dependency edges no longer need fixture/manual construction. After that, broader semantic predecessor heuristics and B04 historical modes can be added without weakening the explicit-provenance boundary.
