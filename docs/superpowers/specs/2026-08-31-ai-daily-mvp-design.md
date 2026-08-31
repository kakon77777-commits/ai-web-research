# AI Daily MVP — Series B Vertical Slice Design

**Status:** Approved from Series B TW-B / AI Daily MVP slice
**Date:** 2026-08-31
**Base:** `integration/ausi-runtime-core-v0.1` at `924d6bd8d0d0c2984f815709f1cd6758adcd34e3`

## Goal

Add one minimal, deterministic, testable vertical slice on top of the existing AUSI runtime:

```text
CandidateEvidence
→ CanonicalClaim
→ CanonicalEvent
→ KnowledgeState
→ DailyBatch
→ zh-Hant script + machine JSON
→ correction lookup
```

This slice proves that the existing Trusted Data / Evidence runtime can feed a canonical research state and that one canonical state can drive more than one publication projection without re-researching the source corpus.

## Scope

### In scope

- generic canonical Claim / Event / KnowledgeState contracts;
- append-oriented SQLite storage for claims, event revisions, knowledge states, projection artifacts and correction dependencies;
- minimal AI Industry entity/event enums and deterministic event materialization helpers;
- deterministic daily selection using explicit importance/freshness/confidence inputs;
- `SYSTEM_AS_KNOWN` knowledge-state snapshots for the MVP;
- machine JSON projection and deterministic Traditional Chinese script projection;
- artifact-to-claim/event lineage;
- correction impact lookup;
- minimal resource budget / anytime-partial result for bounded event selection;
- synthetic end-to-end fixture covering source dependence, rumor status, event dedup, correction propagation and batch-state reuse.

### Out of scope

- a new general web-search provider;
- TTS/video rendering;
- full B04 `PUBLIC_AS_AVAILABLE` and `LATEST_VIEW_OF_PAST` reconstruction;
- full AI Industry graph analytics;
- learned resource-routing policy;
- UI / website frontend;
- Patent-domain changes;
- changes to legacy `src/crawler/*` behavior.

## Existing runtime reuse

The branch inherits PR #1's `src/ai_web_research` runtime. Reuse, do not duplicate:

- `core.types.JsonValue`, `ArtifactRef`, `SearchState`;
- `evidence.models.CandidateEvidence`;
- `evidence.ledger.EvidenceLedger`;
- `storage.trusted_sqlite.TrustedDataStore` for trusted acquisition/evidence objects;
- existing provider/method/execution registries;
- legacy crawler adapters without modification.

The new canonical knowledge store may share the same SQLite file path as `TrustedDataStore`, but uses separate tables and a separate class so evidence-policy storage and canonical knowledge semantics remain independently testable.

## New package boundaries

```text
src/ai_web_research/
  knowledge/
    models.py        # Claim/Event/KnowledgeState contracts
    sqlite.py        # append-oriented canonical knowledge tables
  domains/ai_industry/
    models.py        # AI entity/event enums and daily event inputs
    canonicalize.py  # deterministic claim/event promotion helpers
    daily.py         # daily batch selection
  resource_control/
    models.py        # minimal budget + anytime result
  projection/
    models.py        # ProjectionArtifact / CorrectionImpact
    daily.py         # zh-Hant + machine renderers
    registry.py      # artifact lineage + correction lookup
```

## Canonical knowledge contracts

### CanonicalClaim

Required semantics:

- stable `claim_id`;
- natural-language `statement` plus optional structured subject/predicate/object fields;
- typed state: `observed`, `unverified`, `partially_supported`, `well_supported`, `confirmed`, `disputed`, `contradicted`, `superseded`, `withdrawn`, `retracted`;
- one or more evidence IDs for evidence-bearing factual claims;
- `claim_origin`: `source_assertion` or `derived_inference`;
- `known_at` and optional valid-time interval;
- immutable revision number.

### CanonicalEvent

- stable `event_id`;
- `event_type`;
- canonical entity IDs;
- claim/evidence IDs;
- typed status;
- `known_at`, valid time and revision;
- stable event identity across corrections.

### KnowledgeState

MVP supports `SYSTEM_AS_KNOWN` only. State stores:

- `state_id`;
- `as_of`;
- policy version;
- event IDs and claim IDs included in the batchable state.

## Append-oriented storage

No destructive historical overwrite. Updates are inserted as higher revisions. Store APIs return latest revision by default and can list history.

Tables:

```text
canonical_claim_revisions
canonical_event_revisions
knowledge_states
projection_artifacts
projection_dependencies
```

## AI Daily selection

The selector operates only on canonical events/claims; it never reads raw documents.

Each daily candidate supplies explicit normalized values:

```text
importance ∈ [0,1]
freshness ∈ [0,1]
audience_relevance ∈ [0,1]
confidence ∈ [0,1]
```

Deterministic score:

```text
0.35*importance + 0.25*freshness + 0.20*audience_relevance + 0.20*confidence
```

Confirmed/well-supported items are eligible for the main brief. Unverified/rumor items may only appear in a separately labeled `what_to_watch` section when explicitly enabled.

## Resource bound / anytime behavior

MVP budget is deliberately small: `max_selected_events` and `max_watch_events`. If more eligible events exist than budget permits, the builder returns a valid partial batch with:

```text
complete = false
stop_reason = budget_exhausted
open_event_ids = (...)
```

The batch remains publishable because every selected item is already canonical.

## Projection

### Machine JSON

Contains batch ID, knowledge state ID, selected event/claim IDs, explicit statuses and lineages.

### Traditional Chinese script

Deterministic renderer emits one segment per selected event. Every segment stores its claim/event IDs. Status labels are non-droppable:

- `confirmed` → `已確認`
- `well_supported` → `多方支持`
- `unverified` / rumor watch → `尚未確認`
- `disputed` → `資訊有爭議`

No projection step may upgrade status.

## Correction propagation

Projection artifacts register claim/event dependencies. When a claim revision is inserted with state `contradicted`, `superseded`, `withdrawn`, or `retracted`, querying by claim ID returns every affected artifact. The registry does not auto-edit external media; it provides deterministic impact discovery for channel-specific remediation.

## MVP fixture

Synthetic scenario:

1. A news sensor says Model X was released under License L1.
2. Official blog confirms the model release.
3. Official repository confirms the release and later shows License L2.
4. Two syndicated media articles repeat the same press release; they are represented as dependent evidence and do not increase independent-root count.
5. API availability is announced but not operationally confirmed; it is not projected as fully available.
6. Initial daily batch publishes the confirmed model-release claim.
7. A later license correction creates a new claim revision and the artifact registry identifies the affected script artifact.

## Acceptance criteria

1. Every projected factual claim references canonical evidence IDs.
2. Evidence IDs remain external to projection; projection does not become evidence.
3. Dependent media do not inflate `independent_root_count`.
4. Rumor/unverified state is preserved and separately labeled.
5. Same-event candidates can converge on one stable event ID.
6. Every script segment maps to claim/event IDs.
7. Claim correction can locate affected artifacts.
8. Budget exhaustion returns usable partial state.
9. Failed/nonexistent upstream provider state is not required to mutate canonical storage; store operations are transactional at their own boundary.
10. All artifacts in one batch share one `KnowledgeStateID`.

## Testing

Use `pytest` under `tests/ausi/`. Tests are deterministic and network-free. Each implementation task follows RED → GREEN and ends with `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi -q` where possible.
