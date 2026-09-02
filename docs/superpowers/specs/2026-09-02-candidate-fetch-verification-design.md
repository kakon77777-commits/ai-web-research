# Candidate Fetch + Verification Loop — Design v0.1

## Goal

Close the B02 reverse-source loop after provider-neutral trace search:

```text
Trace DiscoveryCandidate
→ policy-aware fetch
→ bounded FetchedPage
→ page-signal extraction
→ cross-page verification
→ verified SourceRelation
→ SourceFamilyResolution update
```

Search hits remain discovery-only and cannot directly mutate provenance.

## Architecture

Add a separate `candidate_verification` layer after `trace_execution`. Search execution and verification have different authority boundaries: search expands frontier; verification may create source relations only after successful fetch and cross-page evidence checks.

### Fetch compiler

A trace `DiscoveryCandidate` compiles to the existing:

```text
method.fetch_document@1.0.0
ActionKind.FETCH
ArtifactKind.CANDIDATE
```

Fetch binding selection is provider-neutral and deterministic. Optional provider preferences may be supplied; no crawler-specific logic is embedded in the verifier.

### Policy-aware execution

Candidate fetches pass through the supplied `TrustedExecutionRuntime`. Failed/rejected/unavailable candidates are typed results; sibling candidates remain usable.

Only successfully materialized `DOCUMENT` assets are bridged through the existing bounded `fetched_page_from_asset(...)` path. The verifier never refetches URLs itself.

## Verification levels

### 1. Explicit URL predecessor

If the source page already contains a linked textual attribution (`ATTRIBUTED_URL`) and the fetched candidate URL is that exact normalized URL, successful fetch verifies the predecessor target.

Result:

```text
DERIVED_FROM
inference_type = EXPLICIT
confidence = 1.0
```

The relation is created only after fetch succeeds; the source-side attribution signal and fetch verification IDs are retained in `signals`.

### 2. Recovered predecessor

For search-recovered candidates without an explicit source URL, a collapsing relation requires both:

```text
exact quote match
AND
attribution entity ↔ candidate owner/publisher match
```

Result:

```text
DERIVED_FROM
inference_type = INFERRED
confidence = 0.95
```

One signal alone is insufficient:

- quote only → `RELATED_ONLY`
- owner/entity only → `RELATED_ONLY`
- search rank/title/snippet only → no verification value

The inferred relation keeps the quote signal ID, attribution-entity signal ID, candidate owner signal ID, and verification ID.

## Quote matching

Quote matching is deterministic and bounded:

- Unicode casefold;
- whitespace normalization;
- HTML text extraction only from the already-bounded `FetchedPage`;
- exact normalized substring match;
- no fuzzy, embedding, OCR, or LLM similarity.

## Entity/owner matching

Entity matching is deterministic:

- casefold;
- strip punctuation to spaces;
- normalize whitespace;
- exact normalized equality against `CompiledPageSourceSignals.owner_hints`.

Domain-name similarity alone is not sufficient.

## Candidate limits

Default limits:

```text
max candidates per trace execution = 3
max total candidate fetches per verification run = 8
```

Candidates are processed deterministically by `(provider_rank, url)` after URL deduplication.

## Graph update

Verification produces new candidate `SourceNode`s and verified `SourceRelation`s. A new `SourceFamilyResolution` is computed from:

```text
existing source nodes
+ fetched candidate source nodes
+ existing source relations
+ verified predecessor relations
```

The layer reports `independent_root_count_before/after` for the caller-supplied evidence source IDs.

It does not silently rewrite an already-published `CanonicalClaim` or projection artifact in v0.1. Canonical claim revision/reprojection remains a later explicit state-transition slice.

## AI Daily integration

Add a thin wrapper that consumes `AIDailyReverseTraceResult` and returns:

```text
AIDailyVerifiedTraceResult(
    reverse_trace_result,
    candidate_verification_batches,
    updated_source_relations,
    updated_family_resolution,
    independent_root_count_before,
    independent_root_count_after,
)
```

The existing Daily artifact remains attached to the original canonical state; verification state is separately visible and auditable.

## Acceptance Criteria

- CF-01 candidate URL compiles to existing `method.fetch_document@1.0.0`.
- CF-02 fetch binding selection is provider-neutral and deterministic.
- CF-03 fetch execution goes through policy-aware trusted runtime.
- CF-04 only successful DOCUMENT materializations enter FetchedPage verification.
- CF-05 explicit attributed URL + successful fetch can create `DERIVED_FROM(EXPLICIT)`.
- CF-06 quote-only or owner-only matches cannot create a collapsing relation.
- CF-07 exact quote + exact attribution-entity/owner match creates `DERIVED_FROM(INFERRED)` with typed provenance.
- CF-08 search rank/title/snippet never contributes to relation verification.
- CF-09 failed/rejected candidate fetches are explicit and do not erase successful siblings.
- CF-10 E2E demonstrates frontier candidate → fetch → verification → relation → source-family/root-count update.

## Non-goals

- fuzzy phrase matching;
- embedding similarity;
- plagiarism/copy detection;
- LLM provenance guessing;
- persistent source-graph database;
- automatic canonical claim revision/reprojection;
- B04 historical backfill.
