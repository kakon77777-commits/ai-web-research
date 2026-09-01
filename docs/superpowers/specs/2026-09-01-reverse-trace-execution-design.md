# Reverse Trace Execution v0.1 — Design

## Goal

Execute B02 `EXACT_QUOTE_SEARCH` and `ENTITY_SEARCH` trace actions through the existing provider-neutral AUSI search/runtime contracts without allowing search results or ranking to become provenance.

## Scope

Input is an existing `ReverseTracePlan` produced from explicit fetched-page source signals. v0.1 executes only search-valued trace actions:

- `EXACT_QUOTE_SEARCH`
- `ENTITY_SEARCH`

`DIRECT_PREDECESSOR` remains a direct URL trace handled by the existing explicit relation path.

## Architecture

```text
ReverseTracePlan
→ TraceActionCompiler
→ method.lexical_search SearchAction
→ enabled MethodBinding
→ TrustedExecutionRuntime
→ ProviderObservation
→ DiscoveryCandidate normalization
→ TraceExecutionResult
```

The search execution layer is a frontier-expansion layer only. It never emits `SourceRelation` from search rank, title, snippet, URL similarity, or quote/entity hit alone.

## Provider neutrality

The compiler targets `method.lexical_search@1.0.0`, not Brave Search. A binding selector chooses an enabled provider binding for the method. v0.1 supports deterministic provider preference ordering, with Brave as a normal registered binding rather than a special case.

## Policy boundary

Execution uses `TrustedExecutionRuntime`, `PolicyContext`, and existing source policy profiles. The runner must not construct an unconditional `AuthorizedAction` or call provider adapters directly.

## Core types

### `TraceSearchAction`

Wraps one source trace action and the compiled `SearchAction` so lineage from source signal → trace action → provider action is retained.

### `TraceSearchExecution`

Stores:

- source id;
- trace action id/kind;
- compiled search action id;
- provider/binding ids;
- normalized `DiscoveryBatch`;
- policy decision / failure status;
- no source relation.

### `TraceExecutionBatch`

Groups all executions for one `ReverseTracePlan`, preserving skipped `DIRECT_PREDECESSOR` actions separately.

## Binding selection

Selection rules:

1. method must be `method.lexical_search@1.0.0`;
2. binding must be enabled;
3. provider/surface must exist in the registry snapshot;
4. optional `provider_preferences` are applied in order;
5. otherwise choose deterministically by `(provider_id, binding_id)`;
6. no compatible binding → fail closed with `TraceExecutionUnavailable`.

## Query mapping

- `EXACT_QUOTE_SEARCH`: use the quoted query already present in `TraceAction.query`.
- `ENTITY_SEARCH`: use the entity/keyword query already present in `TraceAction.query`.
- `DIRECT_PREDECESSOR`: not compiled as lexical search.

Each compiled action uses:

```text
ActionKind.SEARCH
ArtifactKind.QUERY input
expected_effects = candidate_set_created, source_frontier_expanded
created_by = reverse_trace.runner.v0.1
```

## Candidate semantics

Provider observations are normalized through the existing discovery normalizer. Search candidates remain:

```text
evidence_role = discovery_only
```

A candidate URL may later be fetched and produce new explicit page signals, but the search hit itself never materializes a dependency edge.

## Execution and failures

Per trace action, v0.1 records one of:

- `succeeded`
- `policy_rejected`
- `provider_failed`
- `unavailable`

A failure in one trace branch does not erase other successful branches. The batch remains anytime-usable.

## E2E pressure fixture

Fetched media page contains:

```text
quote: "Distinctive Model X launch wording..."
attribution entity: Official Lab
```

The runtime generates two trace actions and executes both against an injected lexical-search provider observation. Search returns candidate official blog/repository URLs. The acceptance condition is:

1. candidates are surfaced in the trace execution batch;
2. no new `SourceRelation` is produced from search hits;
3. independent-root count remains unchanged until fetched-page verification supplies explicit lineage;
4. after a simulated fetched official page is processed through the existing page-signal path, explicit lineage can change the family resolution.

## Non-goals

- no fuzzy predecessor scoring;
- no embedding-based copy detection;
- no automatic source-edge creation from search rank;
- no full general-purpose B01 planner rewrite;
- no automatic fetch loop beyond returning verified candidate frontier;
- no B04 historical backfill in this slice.

## Acceptance criteria

- RX-01 quote/entity trace actions compile to existing lexical-search method.
- RX-02 direct-predecessor actions are not sent through lexical search.
- RX-03 binding selection is deterministic and provider-neutral.
- RX-04 execution passes through existing policy-aware trusted runtime.
- RX-05 provider observation normalizes into discovery candidates.
- RX-06 candidates remain discovery-only and produce no evidence objects by this layer.
- RX-07 search rank/title/snippet do not create source relations.
- RX-08 branch failure is explicit and does not erase sibling execution results.
- RX-09 trace action → search action → provider observation lineage is retained.
- RX-10 E2E proves search expands frontier while source-family collapse remains gated on later explicit fetched-page provenance.