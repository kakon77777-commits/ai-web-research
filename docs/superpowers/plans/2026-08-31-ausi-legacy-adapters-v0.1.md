# AUSI Legacy Adapters & Execution v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first AUSI MethodBindings executable by adding the minimal authorization wrapper, execution/observation contracts, adapter registry/runtime, and concrete adapters over the repository's existing search capabilities without changing legacy behavior.

**Architecture:** `SearchPlan` still proposes actions. A minimal `AuthorizedAction` wrapper is the only input accepted by the execution runtime. `AdapterRegistry` resolves the adapter named by `MethodBinding`; each concrete legacy adapter lazily imports or receives the existing function and converts its result to typed `ProviderObservation` artifacts. All external results remain observations/candidates; semantic extraction remains `EVIDENCE_CANDIDATE`, never verified evidence.

**Tech Stack:** Python >=3.11 stdlib contracts, existing crawler package, pytest.

**Spec:** AUSI WP-01/WP-02; policy/evidence semantics beyond the minimal execution boundary remain deferred to WP-03 implementation.

## Global Constraints

- Keep `src/crawler/*` behavior unchanged.
- No new runtime dependencies.
- `Plan != Authorization != Execution`.
- Only ALLOW / ALLOW_WITH_OBLIGATIONS may execute.
- Adapter lookup must be exact by `(adapter_id, adapter_version)`.
- Adapters must reject actions whose binding/adapter identity does not match their contract.
- Credentials/secrets never appear in observations.
- `ProviderObservation != VerifiedEvidence`.
- `llm_recall` output is explicitly typed `source_type=llm_recall`, `external_evidence=false`.
- semantic extraction produces `ArtifactKind.EVIDENCE_CANDIDATE` only.
- Legacy imports should be lazy or injectable so the AUSI core remains importable without loading optional legacy dependencies.

---

### Task 1: Execution and authorization contracts

**Files:**
- Create: `src/ai_web_research/execution/__init__.py`
- Create: `src/ai_web_research/execution/models.py`
- Test: `tests/ausi/test_execution_models.py`

**Produces:** `PolicyDecision`, `AuthorizationResult`, `AuthorizedAction`, `ExecutionContext`, `ObservationStatus`, `ProviderObservation`, `ErrorCategory`, `RuntimeErrorRecord`.

- [ ] Write failing tests proving DENY/UNKNOWN/REVIEW are not executable, observations preserve action/provider/surface identity, and credential profile IDs are metadata-only rather than secrets.
- [ ] Run `pytest tests/ausi/test_execution_models.py -q` and verify RED.
- [ ] Implement minimal frozen dataclasses/enums.
- [ ] Run the test and expect PASS.

### Task 2: AdapterRegistry and ExecutionRuntime

**Files:**
- Create: `src/ai_web_research/execution/registry.py`
- Create: `src/ai_web_research/execution/runtime.py`
- Test: `tests/ausi/test_execution_runtime.py`

**Produces:** `ProviderAdapter` protocol, `AdapterRegistry`, `AdapterVersionConflict`, `AdapterNotFound`, `ExecutionRejected`, `ExecutionRuntime`.

- [ ] Write failing tests for exact adapter resolution, conflicting re-registration, non-allowed action rejection, and one successful adapter execution.
- [ ] Run RED.
- [ ] Implement minimal registry/runtime.
- [ ] Run GREEN.

### Task 3: Local corpus and LLM legacy adapters

**Files:**
- Create: `src/ai_web_research/providers/legacy/__init__.py`
- Create: `src/ai_web_research/providers/legacy/local.py`
- Create: `src/ai_web_research/providers/legacy/llm.py`
- Test: `tests/ausi/test_legacy_local_llm_adapters.py`

**Produces:** `LegacyIdentitySearchAdapter`, `LegacyLexicalSearchAdapter`, `LegacyDivergenceAdapter`, `LegacyLlmRecallAdapter`.

- [ ] Write failing tests with injected fake legacy callables so no network/Vertex dependency is required.
- [ ] Verify identity-search maps folded objects to `CANDIDATE` artifacts and preserves paths/score metadata.
- [ ] Verify lexical adapter performs one-query local search without divergence.
- [ ] Verify divergence returns one `QUERY_SET` artifact.
- [ ] Verify LLM recall returns candidates tagged `source_type=llm_recall` and `external_evidence=false`.
- [ ] Implement minimal adapters using lazy imports as defaults.
- [ ] Run GREEN.

### Task 4: Crawler/fetch and semantic-extraction adapters + built-in registration

**Files:**
- Create: `src/ai_web_research/providers/legacy/crawler.py`
- Create: `src/ai_web_research/providers/legacy/extraction.py`
- Create: `src/ai_web_research/providers/legacy/register.py`
- Modify: `src/ai_web_research/providers/builtin.py`
- Test: `tests/ausi/test_legacy_crawler_extraction_adapters.py`
- Test: `tests/ausi/test_builtin_adapter_registration.py`

**Produces:** `LegacyCrawlAdapter`, `LegacyFetchAdapter`, `LegacySemanticExtractionAdapter`, `register_legacy_adapters`.

- [ ] Write failing tests with injected crawl/extract callables.
- [ ] Verify crawl returns a `CANDIDATE_SET` summary observation without pretending pages are evidence.
- [ ] Verify depth-0 fetch uses a copied config and returns a `DOCUMENT` artifact reference.
- [ ] Verify semantic extraction returns `EVIDENCE_CANDIDATE`, preserving quote-verification and validation metadata.
- [ ] Verify every enabled built-in binding resolves an exact registered adapter.
- [ ] Implement minimal adapters and registration.
- [ ] Run `pytest tests/ausi -q` and expect all AUSI tests PASS.
- [ ] Run `python -m compileall -q src/ai_web_research tests/ausi`.

### Task 5: PR verification and handoff

- [ ] Compare branch to `master`; confirm no `src/crawler/*` modifications.
- [ ] Update PR #1 with new scope and fresh test counts.
- [ ] Re-check mergeability/status.
- [ ] Produce downloadable source pack containing the canonical AUSI namespace/tests and packaging file.
