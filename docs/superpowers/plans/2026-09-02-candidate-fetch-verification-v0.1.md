# Candidate Fetch + Verification v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch reverse-trace discovery candidates through the existing trusted runtime, verify high-precision predecessor evidence on fetched pages, and update source-family state only after verification.

**Architecture:** Add a separate `source_graph/candidate_verification.py` layer after `trace_execution.py`. It compiles candidates to existing `method.fetch_document` actions, executes them through `TrustedExecutionRuntime`, bridges successful DOCUMENT assets to `FetchedPage`, performs deterministic cross-page verification, and returns verified relations plus updated in-memory family state. AI Daily receives a thin downstream wrapper; search execution remains unchanged.

**Tech Stack:** Python 3.13, dataclasses, existing AUSI core contracts, pytest, stdlib HTML/parser utilities already present.

**Spec:** `docs/superpowers/specs/2026-09-02-candidate-fetch-verification-design.md`

## Global Constraints

- Search candidates remain `discovery_only` and never directly create provenance.
- Fetch uses existing `method.fetch_document@1.0.0` and `TrustedExecutionRuntime`.
- No new runtime dependency.
- No fuzzy/embedding/LLM predecessor inference.
- Exact quote alone or owner/entity alone cannot create a collapsing relation.
- Graph mutation is append-like output from this layer; no automatic CanonicalClaim rewrite.
- Default candidate limits: 3 per trace execution, 8 total per run.

---

### Task 1: Candidate → FetchAction compiler

**Files:**
- Create: `src/ai_web_research/source_graph/candidate_verification.py`
- Test: `tests/ausi/test_candidate_fetch_action_compiler.py`

**Interfaces:**
- Consumes: `DiscoveryCandidate`, `ProviderRegistrySnapshot`, `MethodBinding`.
- Produces: `TraceCandidateFetchAction`, `select_fetch_binding(...)`, `compile_candidate_fetch_action(...)`.

- [ ] Write tests proving a candidate compiles to `method.fetch_document@1.0.0`, `ActionKind.FETCH`, and `ArtifactKind.CANDIDATE` with URL metadata.
- [ ] Test optional provider preference and deterministic fallback.
- [ ] Test disabled/non-fetch bindings are ignored and no binding fails closed.
- [ ] Run the new test and observe RED because the module/API does not exist.
- [ ] Implement the minimal compiler and selector.
- [ ] Run the test to GREEN.
- [ ] Commit test then implementation as separate TDD-visible commits.

### Task 2: Policy-aware candidate fetch runner

**Files:**
- Modify: `src/ai_web_research/source_graph/candidate_verification.py`
- Test: `tests/ausi/test_candidate_fetch_runner.py`

**Interfaces:**
- Consumes: `TraceCandidateFetchAction`, `TrustedExecutionRuntime`, `ExecutionContext`, `PolicyContext`, injected `TextReader`.
- Produces: typed `CandidateFetchExecution` with status, fetched page or failure.

- [ ] Test successful trusted execution only accepts a materialized `DOCUMENT` asset and bridges it through `fetched_page_from_asset(...)`.
- [ ] Test policy rejection, provider failure, non-DOCUMENT result, and no local content ref are typed failures under `fail_fast=False`.
- [ ] Test sibling execution is not implied by a single failure.
- [ ] Run RED.
- [ ] Implement minimal runner with statuses `FETCHED`, `POLICY_REJECTED`, `PROVIDER_FAILED`, `INVALID_DOCUMENT`, `UNAVAILABLE`.
- [ ] Run GREEN and commit.

### Task 3: Cross-page predecessor verification

**Files:**
- Modify: `src/ai_web_research/source_graph/candidate_verification.py`
- Test: `tests/ausi/test_candidate_predecessor_verification.py`

**Interfaces:**
- Consumes: source `FetchedSourcePageResult`, fetched candidate page, originating trace action/execution.
- Produces: `PredecessorVerification` and optional verified `SourceRelation`.

- [ ] Test explicit attributed URL + fetched exact URL creates `DERIVED_FROM(EXPLICIT, 1.0)`.
- [ ] Test exact quote only returns `RELATED_ONLY` and no relation.
- [ ] Test entity-owner match only returns `RELATED_ONLY` and no relation.
- [ ] Test exact quote + exact normalized attribution-entity/owner match creates `DERIVED_FROM(INFERRED, 0.95)`.
- [ ] Test search rank/title/snippet never affect verification.
- [ ] Test quote/entity normalization is deterministic and bounded.
- [ ] Run RED.
- [ ] Implement HTML-to-text normalization and verification logic.
- [ ] Run GREEN and commit.

### Task 4: Verification batch, dedup, limits, and family update

**Files:**
- Modify: `src/ai_web_research/source_graph/candidate_verification.py`
- Test: `tests/ausi/test_candidate_verification_batch.py`

**Interfaces:**
- Consumes: `AIDailyReverseTraceResult`, source page results, provider registry/runtime/policy, evidence source IDs.
- Produces: `CandidateVerificationBatch` / `VerifiedTraceGraphUpdate`.

- [ ] Test candidate URL dedup across quote/entity branches.
- [ ] Test deterministic `(provider_rank, url)` ordering.
- [ ] Test 3-per-execution and 8-total limits.
- [ ] Test one failed fetch does not erase verified siblings.
- [ ] Test updated relation set recomputes `SourceFamilyResolution` and reports before/after root counts.
- [ ] Run RED.
- [ ] Implement batch executor and family update.
- [ ] Run GREEN and commit.

### Task 5: AI Daily E2E pressure fixture

**Files:**
- Create: `tests/ausi/fixtures/ai_daily_candidate_verification_scenario.py`
- Create: `tests/ausi/test_ai_daily_candidate_verification_e2e.py`
- Modify: `src/ai_web_research/domains/ai_industry/live_discovery.py`

**Interfaces:**
- Consumes: existing `AIDailyReverseTraceResult`.
- Produces: `AIDailyVerifiedTraceResult` through `verify_ai_daily_reverse_trace(...)`.

- [ ] Create a fixture where Media A contains `According to Official Example` + a distinctive quote but no original-source URL; Media B syndicates Media A; Official Blog contains the exact quoted text and owner `Official Example`; Official Repo shares owner but not quote.
- [ ] Search execution returns Official Blog and Official Repo candidates.
- [ ] Fetch execution materializes both pages.
- [ ] Assert pre-verification source families count evidence roots as 3.
- [ ] Assert only Official Blog verifies as predecessor and creates one `DERIVED_FROM(INFERRED)` relation.
- [ ] Assert post-verification root count becomes 2.
- [ ] Assert Official Repo remains related-only/no relation.
- [ ] Assert existing Daily KnowledgeStateID/artifact is unchanged in v0.1.
- [ ] Run RED, implement the thin wrapper, run GREEN.
- [ ] Run broad regression over materialized AI Daily/source-graph stack.
- [ ] Commit.

### Task 6: Closure and reviewer evidence

**Files:**
- Create: `docs/AI_DAILY_CANDIDATE_FETCH_VERIFICATION_v0.1.md`

- [ ] Document CF-01..CF-10 with concrete test evidence.
- [ ] Document the critical limitation that canonical claim revision/reprojection is not automatic in v0.1.
- [ ] Fresh-run the broad pytest suite used by this stacked slice.
- [ ] Fresh-run compileall with isolated `PYTHONPYCACHEPREFIX` if required by the sandbox.
- [ ] Compare PR #5 head → candidate-verification head and ensure behind=0.
- [ ] Create stacked PR with exact verification limitations and no unsupported CI claims.
