# Reverse Trace Execution v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute generated exact-quote/entity reverse-trace searches through the existing provider-neutral, policy-aware runtime while keeping search results strictly discovery-only.

**Architecture:** Add a focused `source_graph.trace_execution` module that compiles B02 `TraceAction` objects to existing `method.lexical_search` `SearchAction`s, deterministically selects an enabled binding, executes through `TrustedExecutionRuntime`, and normalizes the returned observation into `DiscoveryBatch`. It returns lineage-rich execution records but no `SourceRelation`; fetched-page verification remains the only path that can later create explicit provenance edges.

**Tech Stack:** Python 3.11+, dataclasses, existing AUSI `SearchAction`, provider/method registries, `TrustedExecutionRuntime`, discovery normalizer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-reverse-trace-execution-design.md`

## Global Constraints

- `SearchResult != Evidence`.
- Search rank/title/snippet/URL similarity never create `SourceRelation` in this slice.
- Compile to existing `method.lexical_search@1.0.0`; no provider-specific search method.
- Execute through existing policy-aware `TrustedExecutionRuntime`; do not directly authorize or call Brave adapter.
- `DIRECT_PREDECESSOR` is not sent through lexical search.
- One failed trace branch must not erase successful sibling branches.
- No changes under `src/crawler/*` or Patent-domain files.
- No new runtime dependency.

---

### Task 1: Deterministic trace-action compiler and binding selector

**Files:**
- Create: `src/ai_web_research/source_graph/trace_execution.py`
- Test: `tests/ausi/test_reverse_trace_action_compiler.py`

**Interfaces:**
- Consumes: `TraceAction`, `TraceActionKind`, `ProviderRegistrySnapshot`, `VersionRef`.
- Produces: `TraceSearchAction`, `select_lexical_binding(...)`, `compile_trace_search_action(...)`.

- [ ] **Step 1: Write failing tests**

Tests must cover:

```python
assert compile_trace_search_action(EXACT_QUOTE_SEARCH).search_action.method_ref == VersionRef("method.lexical_search", "1.0.0")
assert compile_trace_search_action(ENTITY_SEARCH).search_action.action_kind is ActionKind.SEARCH
```

and:

```python
with pytest.raises(TraceActionNotSearchable):
    compile_trace_search_action(DIRECT_PREDECESSOR, ...)
```

Binding tests create two enabled lexical bindings and assert provider preference order wins; without preferences assert deterministic `(provider_id, binding_id)` ordering; no binding raises `TraceExecutionUnavailable`.

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_reverse_trace_action_compiler.py -q
```

Expected: collection/import failure because `source_graph.trace_execution` does not exist.

- [ ] **Step 3: Implement minimal compiler**

`TraceSearchAction` fields:

```python
@dataclass(frozen=True)
class TraceSearchAction:
    source_id: str
    trace_action_id: str
    trace_kind: TraceActionKind
    signal: str
    search_action: SearchAction
```

`select_lexical_binding(providers, provider_preferences=())` filters enabled bindings with method `VersionRef("method.lexical_search", "1.0.0")`, validates provider/surface existence, then chooses preference rank followed by provider/binding lexical order.

`compile_trace_search_action(...)` requires `trace.query`, creates a deterministic `SearchAction` with `ActionKind.SEARCH`, one `ArtifactKind.QUERY` input, and parameters `{"query": trace.query, "top_k": top_k}`.

- [ ] **Step 4: Run GREEN**

Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_research/source_graph/trace_execution.py tests/ausi/test_reverse_trace_action_compiler.py
git commit -m "feat: compile reverse-trace search actions"
```

---

### Task 2: Policy-aware execution runner and candidate normalization

**Files:**
- Modify: `src/ai_web_research/source_graph/trace_execution.py`
- Test: `tests/ausi/test_reverse_trace_execution_runner.py`

**Interfaces:**
- Consumes: `TraceSearchAction`, `TrustedExecutionRuntime`, `ExecutionContext`, `PolicyContext`.
- Produces: `TraceSearchExecution`, `execute_trace_search_action(...)`.

- [ ] **Step 1: Write failing tests**

Use a fake trusted runtime object whose `execute(action, context, policy_context, ...)` records the received `SearchAction` and returns an object containing a deterministic `ProviderObservation` with candidate artifacts.

Assert:

```python
result.discovery_batch.candidates[0].url == "https://official.example/model-x"
result.status is TraceExecutionStatus.SUCCEEDED
result.provider_id == "provider.fake"
```

and every candidate metadata remains discovery-only / no evidence object is returned.

Also assert a `TrustedExecutionRejected`-like failure is represented as `POLICY_REJECTED`, while a provider exception is `PROVIDER_FAILED` when `fail_fast=False`.

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_reverse_trace_execution_runner.py -q
```

Expected: missing runner/status types.

- [ ] **Step 3: Implement minimal runner**

Define:

```python
class TraceExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    POLICY_REJECTED = "policy_rejected"
    PROVIDER_FAILED = "provider_failed"
    UNAVAILABLE = "unavailable"
```

`TraceSearchExecution` stores source/trace/search ids, provider/binding, status, `DiscoveryBatch | None`, error code, and observation id.

`execute_trace_search_action(...)` invokes the supplied trusted runtime; on success normalize `result.observation` with existing `normalize_discovery_observation`.

- [ ] **Step 4: Run GREEN**

Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_research/source_graph/trace_execution.py tests/ausi/test_reverse_trace_execution_runner.py
git commit -m "feat: execute reverse-trace searches through trusted runtime"
```

---

### Task 3: Execute a full ReverseTracePlan with anytime branch isolation

**Files:**
- Modify: `src/ai_web_research/source_graph/trace_execution.py`
- Test: `tests/ausi/test_reverse_trace_plan_execution.py`

**Interfaces:**
- Consumes: `ReverseTracePlan`.
- Produces: `TraceExecutionBatch`, `execute_reverse_trace_plan(...)`.

- [ ] **Step 1: Write failing tests**

Plan fixture contains:

```text
DIRECT_PREDECESSOR
EXACT_QUOTE_SEARCH
ENTITY_SEARCH
```

Assert direct predecessor appears in `skipped_action_ids`, the other two execute, and one provider failure still leaves the sibling result in the batch.

`TraceExecutionBatch` must expose:

```text
source_id
executions
skipped_action_ids
complete
failure_count
candidate_count
```

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_reverse_trace_plan_execution.py -q
```

Expected: missing batch/plan executor.

- [ ] **Step 3: Implement plan executor**

Iterate trace actions in deterministic plan order. Compile searchable actions using one selected binding per batch. Execute independently with `fail_fast=False`. `complete=False` if any searchable branch failed; direct predecessor skip does not make the batch incomplete.

- [ ] **Step 4: Run GREEN**

Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_research/source_graph/trace_execution.py tests/ausi/test_reverse_trace_plan_execution.py
git commit -m "feat: add anytime reverse-trace plan execution"
```

---

### Task 4: Wire execution into fetched-page AI Daily without granting provenance

**Files:**
- Modify: `src/ai_web_research/domains/ai_industry/live_discovery.py`
- Test: `tests/ausi/test_ai_daily_reverse_trace_execution_e2e.py`
- Create fixture: `tests/ausi/fixtures/ai_daily_trace_execution_scenario.py`

**Interfaces:**
- Consumes: existing fetched-page extraction result + `execute_reverse_trace_plan`.
- Produces: `AIDailyTraceExpansionResult` or equivalent wrapper holding the existing fetched-page result plus trace execution batches.

- [ ] **Step 1: Write failing E2E test**

Fixture page includes one quote and one `According to Official Lab` attribution, producing exact-quote and entity trace actions. Inject provider observations that return official blog and repository candidates.

Assert:

```python
assert trace_candidate_urls == {
    "https://official.example/model-x",
    "https://repo.example/model-x",
}
```

but:

```python
assert result.discovery_result.source_relations == fetched_page_explicit_relations_only
assert result.discovery_result.canonical_claim.independent_root_count == before_search_root_count
```

Search hits must not alter source-family resolution.

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_ai_daily_reverse_trace_execution_e2e.py -q
```

Expected: missing expansion wrapper.

- [ ] **Step 3: Implement minimal integration wrapper**

The wrapper first calls existing `build_ai_daily_from_fetched_pages`, then executes each generated plan against the trusted runtime. It returns trace expansion data separately; it does **not** re-run family resolution with search candidates and does not create relations.

- [ ] **Step 4: Run GREEN and regression**

```bash
PYTHONPATH=src python -m pytest -p no:cacheprovider \
  tests/ausi/test_reverse_source_trace.py \
  tests/ausi/test_page_source_signal_extraction.py \
  tests/ausi/test_page_source_relation_compile.py \
  tests/ausi/test_ai_daily_fetched_source_e2e.py \
  tests/ausi/test_reverse_trace_action_compiler.py \
  tests/ausi/test_reverse_trace_execution_runner.py \
  tests/ausi/test_reverse_trace_plan_execution.py \
  tests/ausi/test_ai_daily_reverse_trace_execution_e2e.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_research/domains/ai_industry/live_discovery.py tests/ausi/fixtures/ai_daily_trace_execution_scenario.py tests/ausi/test_ai_daily_reverse_trace_execution_e2e.py
git commit -m "feat: expand AI Daily reverse-trace frontier via runtime"
```

---

### Task 5: Reviewer document, acceptance report, and closure verification

**Files:**
- Create: `docs/AI_DAILY_REVERSE_TRACE_EXECUTION_v0.1.md`

**Interfaces:**
- Documents RX-01..RX-10 and verification boundary.

- [ ] **Step 1: Run fresh available test suite**

Run the broadest locally materialized `tests/ausi` subset plus new tests. Record exact pass count; do not reuse historical PR counts.

- [ ] **Step 2: Compile**

```bash
PYTHONPATH=src python -m compileall -q src/ai_web_research tests/ausi
```

Expected exit 0 for the locally materialized package.

- [ ] **Step 3: Verify diff isolation**

Compare PR #4 head to feature head and assert no `src/crawler/*` or Patent-domain changes.

- [ ] **Step 4: Write reviewer document**

Record acceptance checklist, fresh commands/results, branch/base SHAs, no-credential limitation if Brave cannot perform authenticated live request, and the key invariant that search results expanded frontier but changed zero source relations.

- [ ] **Step 5: Commit**

```bash
git add docs/AI_DAILY_REVERSE_TRACE_EXECUTION_v0.1.md
git commit -m "docs: add reverse-trace execution acceptance report"
```

## Self-review

- Spec coverage: RX-01..RX-10 map to Tasks 1–5.
- Placeholder scan: no TBD/TODO implementation holes.
- Type consistency: all actions compile to existing `SearchAction`; all execution enters `TrustedExecutionRuntime`; all outputs normalize through existing `DiscoveryBatch`.
- Scope: no full planner rewrite, fuzzy lineage, automatic fetch loop, or B04 backfill.