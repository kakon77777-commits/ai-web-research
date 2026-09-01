# AI Daily — Candidate Fetch + Verification v0.1

## Scope

This slice closes the reverse-source loop after provider-neutral trace search:

```text
Trace DiscoveryCandidate
→ method.fetch_document
→ policy-aware TrustedExecutionRuntime
→ bounded FetchedPage
→ cross-page predecessor verification
→ verified SourceRelation
→ SourceFamilyResolution update
```

Search hits remain discovery-only. Graph mutation is allowed only after successful fetch and cross-page verification.

## Acceptance

- **CF-01 PASS** — candidate URL compiles to existing `method.fetch_document@1.0.0`, `ActionKind.FETCH`, `ArtifactKind.CANDIDATE`.
- **CF-02 PASS** — fetch binding selection is provider-neutral, preference-aware, deterministic, and fail-closed.
- **CF-03 PASS** — candidate fetch goes through the supplied policy-aware trusted runtime.
- **CF-04 PASS** — only successfully materialized DOCUMENT assets enter bounded FetchedPage verification.
- **CF-05 PASS** — explicit attributed URL + successful fetch can produce `DERIVED_FROM(EXPLICIT, 1.0)`.
- **CF-06 PASS** — quote-only and owner/entity-only matches remain `RELATED_ONLY` and create no collapsing relation.
- **CF-07 PASS** — exact quote + exact attribution-entity/owner match produces `DERIVED_FROM(INFERRED, 0.95)` with verification/signal lineage.
- **CF-08 PASS** — search rank/title/snippet are not verification inputs and cannot support a relation.
- **CF-09 PASS** — failed/rejected fetches are typed; successful sibling records survive.
- **CF-10 PASS** — AI Daily E2E demonstrates candidate search → fetch → verification → inferred predecessor relation → root count `3 → 2`.

## Critical authority boundary

The verification layer may update in-memory source graph/family state, but v0.1 intentionally does **not** mutate the already-created canonical claim or Daily artifact.

Pressure fixture result:

```text
source-family roots before verification = 3
source-family roots after verification  = 2
existing CanonicalClaim.independent_root_count = 3
existing Daily KnowledgeStateID = unchanged
```

This is deliberate. A later explicit state-transition slice must append a claim revision and then invoke B08 correction/reprojection. Historical publication state is not silently rewritten.

## Predecessor rules

### Explicit

```text
source ATTRIBUTED_URL exact candidate URL
+ successful candidate fetch
→ DERIVED_FROM / EXPLICIT / confidence 1.0
```

### Recovered

```text
exact normalized source quote found in fetched candidate visible text
AND
source attribution entity == candidate owner/publisher hint
→ DERIVED_FROM / INFERRED / confidence 0.95
```

Insufficient evidence:

```text
quote only → RELATED_ONLY
owner/entity only → RELATED_ONLY
search rank/title/snippet → no verification value
```

## Resource bounds

Default:

```text
max candidates per search execution = 3
max candidate fetches per verification run = 8
```

Direct predecessor URLs are queued before search candidates. Search candidates are sorted deterministically by `(provider_rank, url, candidate_id)` and URL-deduplicated before fetch.

## Fresh verification

Freshly rerun immediately before closure on the locally materialized AI Daily / discovery / source-graph stack:

```text
85 passed in 0.23s
```

Compile verification:

```text
PYTHONPYCACHEPREFIX=/tmp/ai_web_research_candidate_verify_compile \
PYTHONPATH=src python -m compileall -q src/ai_web_research tests/ausi

exit 0
```

The host Python environment prints an unrelated spreadsheet-runtime warmup warning; both verification commands exited 0.

## Verification limitations

- The sandbox-local workspace is materialized/reconstructed rather than a complete repository clone.
- Historical PR test counts are not relabeled as fresh results.
- No independent subagent code review is claimed.
- No authenticated Brave live request is claimed when `BRAVE_SEARCH_API_KEY` is absent.
- This slice does not perform automatic CanonicalClaim revision/reprojection after graph convergence.

## Next slice

Explicitly convert verified graph-state changes into append-only canonical research-state changes:

```text
VerifiedTraceGraphUpdate
→ Claim Revision Proposal
→ append CanonicalClaim revision
→ new KnowledgeState delta
→ affected ProjectionArtifact lookup
→ correction/reprojection
```

Old Daily artifacts remain historical records rather than being silently overwritten.
