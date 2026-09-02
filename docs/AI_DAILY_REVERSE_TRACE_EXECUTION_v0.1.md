# AI Daily Reverse Trace Execution v0.1 — Acceptance Report

## Scope

This slice executes B02 `EXACT_QUOTE_SEARCH` and `ENTITY_SEARCH` actions through the existing provider-neutral, policy-aware AUSI runtime.

```text
Fetched page signals
→ ReverseTracePlan
→ lexical SearchAction
→ MethodBinding
→ TrustedExecutionRuntime
→ ProviderObservation
→ DiscoveryCandidate frontier
```

The output is candidate frontier expansion only. Search results do not mutate the source graph, source-family resolution, canonical claim state, or independent-root count.

## Core boundary

```text
SearchResult != Evidence
SearchHit != Provenance
SearchRank != SourceDependency
```

`DIRECT_PREDECESSOR` remains on the existing explicit-URL path and is never sent through lexical search.

## Provider-neutral compilation

Searchable trace actions compile to:

```text
method.lexical_search@1.0.0
ActionKind.SEARCH
ArtifactKind.QUERY
```

No Brave-specific method is created. Binding selection filters enabled lexical bindings, validates provider/surface existence, applies optional provider preference ordering, then falls back deterministically to `(provider_id, binding_id)` ordering.

## Policy-aware execution

The runner calls the supplied `TrustedExecutionRuntime.execute(...)` with the compiled `SearchAction`, `ExecutionContext`, and `PolicyContext`. It does not construct an unconditional authorization and does not call provider adapters directly.

Per-branch status:

```text
succeeded
policy_rejected
provider_failed
unavailable
```

A failed branch does not erase successful sibling branches. `TraceExecutionBatch.complete` becomes false while successful discovery candidates remain available.

## Evidence boundary verification

The existing trusted runtime may materialize an authorized provider artifact as an `AcquiredAsset`, but the existing evidence materializer contains this gate:

```python
artifact = materialized.asset.artifact_ref
if artifact.kind is not ArtifactKind.EVIDENCE_CANDIDATE:
    return CandidateEvidenceMaterialization((), (), (), ())
```

Lexical-search providers, including the Brave Search adapter, return `ArtifactKind.CANDIDATE` with `evidence_role=discovery_only`. Therefore this search-execution slice cannot promote search title/snippet/rank metadata into `CandidateEvidence` through the trusted runtime.

## AI Daily integration

`expand_ai_daily_reverse_trace(...)` consumes the already-built PR #4 `AIDailyFetchedSourceResult`. It executes existing `trace_plans` and attaches `TraceExecutionBatch` objects in a new downstream wrapper.

It intentionally does not:

- rerun canonicalization;
- rerun source-family resolution;
- modify source relations;
- attach search hits as evidence;
- change `independent_root_count`.

## E2E pressure fixture

A fetched media page produces:

```text
DIRECT_PREDECESSOR
EXACT_QUOTE_SEARCH
ENTITY_SEARCH
```

The direct predecessor is skipped by the lexical runner. Injected lexical-search execution returns:

```text
https://official.example/model-x
https://repo.example/model-x
```

Expected behavior:

```text
trace frontier candidates: 2
new source relations from search hits: 0
canonical independent_root_count before search: 2
canonical independent_root_count after search: 2
```

The candidate URLs are eligible for a later fetch/verification loop, but are not provenance by themselves.

## Acceptance criteria

- [x] RX-01 quote/entity trace actions compile to existing lexical-search method.
- [x] RX-02 direct-predecessor actions are not sent through lexical search.
- [x] RX-03 binding selection is deterministic and provider-neutral.
- [x] RX-04 execution passes through existing policy-aware trusted runtime contract.
- [x] RX-05 provider observations normalize into discovery candidates.
- [x] RX-06 candidates remain discovery-only; non-`EVIDENCE_CANDIDATE` artifacts cannot become CandidateEvidence through the existing materializer.
- [x] RX-07 search rank/title/snippet create no source relations.
- [x] RX-08 branch failure is explicit and successful sibling results survive.
- [x] RX-09 trace action → search action → provider observation lineage is retained.
- [x] RX-10 E2E expands the frontier while source-family/canonical-root state remains unchanged.

## Verification boundary

The final fresh test and compile commands are recorded in the PR body after closure verification. The sandbox-local checkout is a materialized test workspace rather than a complete repository clone; historical PR test counts are not relabeled as fresh results.

No authenticated Brave live request is claimed when `BRAVE_SEARCH_API_KEY` is absent.

## Non-goals

- no search-hit-to-source-edge shortcut;
- no fuzzy predecessor inference;
- no embedding copy detection;
- no automatic candidate fetch loop;
- no B04 historical backfill;
- no rewrite of the general B01 planner.

## Next slice

The next natural vertical slice is the **Candidate Fetch + Verification Loop**:

```text
trace search candidate
→ fetch candidate page
→ extract explicit source signals
→ verify predecessor relation
→ only then update source graph/family state
```

This closes the reverse-trace loop without allowing search ranking to become provenance.