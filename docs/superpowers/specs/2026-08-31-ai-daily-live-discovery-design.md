# AI Daily Live Discovery + Source Lineage v0.1 Design

**Status:** Approved continuation of Series B / AI Daily MVP  
**Date:** 2026-08-31  
**Base:** `integration/ai-daily-mvp-v0.1` @ `a22d82e6027e39ce5472f83e9687430c498d06a4`

## Goal

Upgrade the fixture-driven AI Daily canonical MVP into the first provider-backed discovery slice:

```text
Query
→ general live search candidates
→ candidate normalization
→ reverse-source trace planning
→ explicit source-dependency graph
→ source-family collapse
→ independent-root count
→ existing CanonicalClaim / CanonicalEvent
→ existing bounded DailyBatch / projections
```

The slice must not create another runtime and must not modify `src/crawler/*` or Patent behavior.

## Provider choice

Use Brave Search API as the first general live-search provider because it exposes an official Web Search REST endpoint and API-key authentication via `X-Subscription-Token`. The runtime provider remains replaceable through the existing AUSI `MethodBinding` / adapter contracts.

Brave integration is credentialed. The adapter reads the credential at execution time from `ExecutionContext.services["brave_search_api_key"]`; provider specs, receipts, artifacts, and repository files never store the key. Missing credentials fail before any HTTP call.

The provider output is **discovery-only**. Search-result snippets and rankings are candidate-source metadata, not canonical evidence.

## Scope

### In scope

1. `provider.brave_search@1.0.0` and `surface.brave_search.web`.
2. Binding of existing `method.lexical_search@1.0.0` to Brave.
3. Injectable async HTTP transport and deterministic provider tests.
4. Normalized `DiscoveryCandidate` objects extracted from provider observations.
5. Minimal Source Graph objects and explicit dependency relations.
6. Deterministic source-family collapse for `syndicated_from`, `mirrors`, `derived_from`, `translated_from`, and explicit same-origin links.
7. Reverse-trace planning from explicit source signals: outbound attributed source URLs, attribution entity hints, and rare quoted phrases.
8. Search-assisted predecessor candidate discovery using a provider-neutral discovery callable.
9. Automatic independent-root counting from evidence-source IDs and resolved source families.
10. AI Daily workflow helper that uses resolved roots instead of fixture-supplied `independent_root_count`.
11. Network-free E2E fixture covering Brave discovery → predecessor trace → family collapse → canonical release → existing projection.

### Out of scope

- semantic-copy detection with embeddings;
- browser scraping of search-engine HTML;
- full automatic truth/authority scoring;
- general graph database;
- full B04 public/latest historical modes;
- TTS/video;
- learned source-dependency classifier;
- claiming a real Brave request when no credential is available.

## Core invariants

- `Method != Provider`.
- `SearchResult != Evidence`.
- `Source != Evidence != Claim != Event`.
- `MentionCount != IndependentEvidenceCount`.
- `EarliestTimestamp != GuaranteedOrigin`.
- Inferred dependency edges carry explicit confidence and signals.
- Missing predecessor is a legal state and is never invented.
- Provider credentials are runtime-only secrets.
- Search result snippets never become verified evidence.
- Existing AI Daily claim/event/projection semantics remain unchanged.

## Brave provider contract

Provider identifiers:

```text
provider.brave_search@1.0.0
surface.brave_search.web
adapter brave_search.web@1.0.0
binding.lexical_search.brave_search.v1
```

Request:

```text
GET https://api.search.brave.com/res/v1/web/search
X-Subscription-Token: <runtime secret>
q=<query>
count=<1..20>
country=<optional>
search_lang=<optional>
```

The adapter returns `ArtifactKind.CANDIDATE` artifacts with:

```text
url
title
description
provider_rank
source_type = brave_web_search_result
external_source = true
evidence_role = discovery_only
```

No snippet field is promoted to `CandidateEvidence` by this slice.

## Source graph model

### SourceNode

```text
source_id
url
canonical_url
published_at
observed_at
owner_hint
content_hash
metadata
```

### SourceRelation

```text
relation_id
from_source_id
to_source_id
relation_type
confidence
inference_type
signals
```

Relation types relevant to root collapse:

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

## Family resolution

Use deterministic union/find over collapsing dependency edges. The family root is chosen by:

1. a node with no outgoing collapsing predecessor edge, if unique;
2. earliest `published_at` among remaining root candidates when timestamps exist;
3. stable lexical `source_id` tie-break.

Cycles are legal but flagged `cycle_detected=true`; a cyclic family receives a deterministic root ID and `root_resolved=false`.

The family resolver returns:

```text
source_to_family
family_roots
unresolved_families
independent_root_count(source_ids)
```

## Reverse trace planning

`SourceTraceSignals` contains:

```text
attributed_source_urls
attribution_entities
quoted_phrases
```

Planning rules:

1. explicit attributed URL → direct predecessor candidate, no search required;
2. rare quoted phrase → exact-quote search query;
3. attribution entity + claim keywords → entity-restricted query;
4. if no signal exists, keep `origin_unresolved`; do not invent a predecessor.

`ReverseTracePlanner` creates provider-neutral `TraceAction` objects. A discovery callable executes search-type actions and returns normalized `DiscoveryCandidate` objects. Actual dependency is only created when an explicit signal matches a returned candidate; provider rank alone never proves dependency.

## AI Daily integration

Add a helper that computes source independence before existing canonical promotion:

```text
resolved draft
= attach_independent_roots(
    claim_draft,
    evidence_source_ids,
    family_resolution,
  )
```

The existing `promote_claim()` remains the fact/evidence gate. This slice does not weaken its requirement that source assertions carry evidence IDs.

## E2E fixture

Synthetic live-discovery fixture:

1. Query `Model X release` returns four Brave candidates: official blog, official repository, Media A, Media B.
2. Media A explicitly attributes the official blog.
3. Media B is syndicated from Media A.
4. Official repository is independent.
5. Reverse tracing searches one exact quote and resolves Media A → official blog.
6. Family collapse produces two independent roots: official blog family + repository family.
7. Release claim is promoted with `independent_root_count=2`.
8. Existing AI Daily selector publishes the confirmed release.
9. Machine and zh-Hant projections still share one `KnowledgeStateID`.
10. No search snippet is present in canonical evidence IDs.

## Testing

All tests are deterministic and network-free by default. Brave HTTP behavior uses an injected fake async client. A separate optional smoke script may perform a real call only when `BRAVE_SEARCH_API_KEY` is present; absence must be reported as `SKIPPED_NO_CREDENTIAL`, not failure and not success.

Target verification commands:

```text
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_brave_search_provider.py -q
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_source_family.py -q
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_reverse_source_trace.py -q
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_ai_daily_live_discovery_e2e.py -q
PYTHONPATH=src python -m compileall -q src/ai_web_research tests/ausi
```

## Acceptance criteria

- LD-01 Brave adapter requires runtime credential and never serializes it.
- LD-02 Brave search outputs candidates tagged `discovery_only`.
- LD-03 candidate URL/title/rank normalization is deterministic.
- LD-04 explicit syndicated/mirror/derived dependencies collapse into one family.
- LD-05 independent root count is computed from runtime family resolution.
- LD-06 quote/entity reverse-trace actions are provider-neutral.
- LD-07 unresolved origin remains explicit when no predecessor can be proven.
- LD-08 provider ranking alone never creates a dependency edge.
- LD-09 AI Daily canonical claim receives the computed independent-root count.
- LD-10 existing machine + zh-Hant projection semantics remain unchanged.
