# Series B — AI Daily Canonical MVP v0.1

**Status:** Implemented on stacked branch `integration/ai-daily-mvp-v0.1`
**Base:** `integration/ausi-runtime-core-v0.1` (PR #1)
**Date:** 2026-08-31

## Scope

This MVP is the first executable Series B vertical slice on top of the existing AUSI runtime.

```text
Trusted / normalized evidence input
→ CanonicalClaim
→ CanonicalEvent
→ SYSTEM_AS_KNOWN KnowledgeState
→ bounded DailyBatch
→ Traditional Chinese script + machine JSON
→ correction impact lookup
```

It deliberately does **not** add a second runtime core, does not rewrite `src/crawler/*`, and does not modify the Patent domain introduced by PR #1.

## Explicit boundary

The current slice starts from trusted / normalized evidence objects already supplied by the AUSI Trusted Data / Evidence boundary. It does **not** claim that a new general live-web search provider is implemented here.

General live discovery, full reverse-source automation, and the remaining B04 temporal views can be added in later slices without changing this canonical Claim/Event/Projection contract.

## Implemented packages

```text
src/ai_web_research/knowledge/
  models.py
  sqlite.py

src/ai_web_research/domains/ai_industry/
  models.py
  canonicalize.py
  daily.py
  mvp.py

src/ai_web_research/resource_control/
  models.py

src/ai_web_research/projection/
  models.py
  daily.py
  registry.py
```

## Canonical semantics

### Claims

Claim revisions are append-oriented. Same `(claim_id, revision)` + identical content is idempotent; a semantic conflict at the same revision fails closed.

### Events

Events retain stable explicit IDs and append revisions rather than overwriting history.

### Knowledge state

MVP materializes `SYSTEM_AS_KNOWN` only. The enum already reserves `PUBLIC_AS_AVAILABLE` and `LATEST_VIEW_OF_PAST` so future B04 slices do not need to change the object identity contract.

### Daily selection

Main brief eligibility:

- event status = `confirmed`;
- factual claim state = `well_supported` or `confirmed`.

`rumor_detected` + `unverified` claims may enter only the explicit `what_to_watch` section when enabled.

Deterministic selection score:

```text
0.35 * importance
+ 0.25 * freshness
+ 0.20 * audience_relevance
+ 0.20 * confidence
```

Tie-break: stable `event_id`.

### Anytime / budget behavior

The MVP budget uses `max_selected_events` and `max_watch_events`. When more eligible canonical events exist than the budget permits, the batch remains usable and returns:

```text
complete = false
anytime_status = partial
stop_reason = budget_exhausted
open_event_ids = (...)
```

### Projection

`render_zh_hant_daily()` and `render_machine_daily()` both consume the same `DailyBatch` / `KnowledgeStateID`.

Non-droppable status mapping:

```text
confirmed       → 已確認
well_supported  → 多方支持
unverified      → 尚未確認
disputed        → 資訊有爭議
```

Every Traditional Chinese projection unit carries explicit `claim_ids` and `event_ids`.

Projection artifacts are downstream views and are never inserted into the Evidence store as canonical evidence roots.

### Corrections

`ArtifactRegistry` indexes projection lineage. A later claim revision can deterministically find every registered artifact that depended on the claim.

The MVP does not auto-edit already-published external media; it establishes the correction impact boundary needed by later channel adapters.

## Synthetic pressure-test fixture

`tests/ausi/fixtures/ai_daily_release_scenario.py` models:

1. one AI-news sensor;
2. official blog evidence;
3. official repository evidence;
4. two syndicated media references that map to the official-blog root family;
5. a confirmed model-release claim;
6. an unverified next-version rumor;
7. an announced but not operationally confirmed API availability claim;
8. a second confirmed paper event so the daily budget must return a partial batch;
9. a later license correction.

For the release claim:

```text
raw evidence objects = 4
independent root families = 2
```

The two syndicated media references therefore do not increase `independent_root_count`.

## Acceptance criteria

| ID | Result | Executable evidence |
|---|---|---|
| AC-01 projected factual claims have Evidence IDs | PASS | `test_ai_daily_mvp_closes_the_canonical_vertical_slice` |
| AC-02 evidence IDs map to source locators in fixture | PASS | same E2E test |
| AC-03 dependent media do not inflate independent root count | PASS | `4 evidence → independent_root_count == 2` |
| AC-04 rumor/unverified state is preserved | PASS | daily selection + projection tests |
| AC-05 same release event uses one stable canonical event ID | PASS | canonicalization + E2E fixture |
| AC-06 every zh-Hant segment maps to claim/event IDs | PASS | projection + E2E tests |
| AC-07 correction locates affected artifact | PASS | `test_later_claim_correction_locates_affected_daily_artifact` |
| AC-08 budget exhaustion returns usable partial batch | PASS | selection + E2E tests |
| AC-09 upstream failure marker creates no canonical claims/events | PASS | `test_upstream_failure_marker_never_creates_canonical_objects` |
| AC-10 machine + zh-Hant output share KnowledgeStateID | PASS | E2E test |

## Fresh verification in this implementation session

The sandbox cannot clone the complete GitHub repository because outbound DNS to `github.com` is blocked. Therefore this session does **not** claim a fresh rerun of PR #1's full existing AUSI suite or the legacy crawler suite.

The new slice was reconstructed locally against the exact existing contracts it directly imports and verified with deterministic network-free tests:

```text
PYTHONPATH=src python -m pytest -p no:cacheprovider \
  tests/ausi/test_knowledge_store.py \
  tests/ausi/test_ai_industry_canonicalization.py \
  tests/ausi/test_ai_daily_selection.py \
  tests/ausi/test_ai_daily_projection.py \
  tests/ausi/test_ai_daily_mvp_e2e.py -q

21 passed in 0.09s
```

Compile verification:

```text
python -m compileall -q <new knowledge / ai_industry / resource_control / projection modules + tests>
COMPILE_OK
```

PR #1 independently reports its own canonical AUSI baseline verification as `89 passed`; that prior result is not relabeled as a fresh result for this stacked branch.

## Next slices

1. connect a general live discovery provider into the existing AUSI method/provider registry;
2. promote B02 source-dependency/root-family resolution from fixture input into runtime behavior;
3. implement `PUBLIC_AS_AVAILABLE` and `LATEST_VIEW_OF_PAST` state reconstruction;
4. persist projection artifacts/correction dependencies in SQLite;
5. add website/TTS/video channel adapters.
