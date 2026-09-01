# AI Daily MVP v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one deterministic Series B vertical slice on the existing AUSI branch: trusted candidate evidence can be promoted into append-oriented claims/events, captured in one `SYSTEM_AS_KNOWN` state, selected under a bounded daily budget, rendered into Traditional Chinese + machine projections, and traced for later corrections.

**Architecture:** Extend `src/ai_web_research` without changing legacy `src/crawler/*` or Patent behavior. Add a generic `knowledge` package for canonical claims/events/state, a minimal `domains.ai_industry` layer for event types and daily selection, a minimal `resource_control` budget contract, and a `projection` layer with artifact lineage/correction lookup. The canonical knowledge SQLite store may use the same physical DB path as `TrustedDataStore` but owns separate append-oriented tables.

**Tech Stack:** Python >=3.11, stdlib dataclasses / enum.StrEnum / sqlite3 / json, existing `ai_web_research` types, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-ai-daily-mvp-design.md`

## Global Constraints

- Base on PR #1 head `924d6bd8d0d0c2984f815709f1cd6758adcd34e3`; do not reimplement its AUSI core.
- Do not modify legacy `src/crawler/*` behavior.
- Do not modify Patent domain behavior.
- Do not add runtime dependencies.
- `Source != Evidence != Claim != Event`.
- `Inference != Fact`.
- Projection artifacts never become canonical evidence roots.
- Historical claim/event revisions are append-oriented; no destructive overwrite.
- MVP supports `SYSTEM_AS_KNOWN` only but types must not block future B04 modes.
- Status labels are non-droppable in projection.
- All tests are network-free and deterministic.

---

### Task 1: Canonical knowledge models and append-oriented SQLite store

**Files:**
- Create: `src/ai_web_research/knowledge/__init__.py`
- Create: `src/ai_web_research/knowledge/models.py`
- Create: `src/ai_web_research/knowledge/sqlite.py`
- Create: `tests/ausi/test_knowledge_store.py`

**Interfaces:**
- Consumes: `ai_web_research.core.types.JsonValue`.
- Produces: `ClaimState`, `ClaimOrigin`, `EventStatus`, `KnowledgeMode`, `ValidTime`, `CanonicalClaim`, `CanonicalEvent`, `KnowledgeState`, `KnowledgeStore`, `KnowledgeStoreConflict`.

- [ ] **Step 1: Write failing model/store tests.** Cover claim/event construction, append revision 1, append revision 2, latest lookup, full revision history, idempotent identical same-revision write, conflicting same-revision write, and `SYSTEM_AS_KNOWN` state persistence.
- [ ] **Step 2: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_knowledge_store.py -q` and verify RED because `ai_web_research.knowledge` does not exist.
- [ ] **Step 3: Implement `knowledge/models.py`.** Use frozen dataclasses. `CanonicalClaim` fields: `claim_id`, `revision`, `statement`, `subject_id`, `predicate`, `object_value`, `state`, `claim_origin`, `evidence_ids`, `independent_root_count`, `known_at`, `valid_time`, `metadata`. `CanonicalEvent` fields: `event_id`, `revision`, `event_type`, `entity_ids`, `status`, `claim_ids`, `evidence_ids`, `known_at`, `valid_time`, `metadata`. `KnowledgeState`: `state_id`, `mode`, `as_of`, `policy_version`, `claim_ids`, `event_ids`, `metadata`.
- [ ] **Step 4: Implement `knowledge/sqlite.py`.** Create `canonical_claim_revisions`, `canonical_event_revisions`, `knowledge_states`; serialize dataclasses deterministically with sorted JSON; same `(id, revision)` identical payload is idempotent, different payload raises `KnowledgeStoreConflict`; latest queries order by revision descending; history orders ascending.
- [ ] **Step 5: Run** the targeted test and expect PASS.
- [ ] **Step 6: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi -q` and ensure no AUSI regressions.
- [ ] **Step 7: Commit** `feat: add append-only canonical knowledge store`.

### Task 2: AI Industry event contracts and deterministic canonical promotion

**Files:**
- Create: `src/ai_web_research/domains/ai_industry/__init__.py`
- Create: `src/ai_web_research/domains/ai_industry/models.py`
- Create: `src/ai_web_research/domains/ai_industry/canonicalize.py`
- Create: `tests/ausi/test_ai_industry_canonicalization.py`

**Interfaces:**
- Consumes: `CandidateEvidence`, `CanonicalClaim`, `CanonicalEvent`.
- Produces: `AIEntityType`, `AIEventType`, `AIIndustryEntity`, `ClaimDraft`, `EventDraft`, `promote_claim`, `canonicalize_event`.

- [ ] **Step 1: Write failing tests.** `promote_claim` must reject factual/source-assertion drafts with no evidence IDs; allow `derived_inference` without external evidence only when explicitly typed; preserve `independent_root_count`; `canonicalize_event` must produce stable explicit event ID supplied by caller and deduplicate claim/evidence IDs while preserving order.
- [ ] **Step 2: Run** the targeted test and verify RED.
- [ ] **Step 3: Implement AI enums/entities.** Entity types: organization, research_lab, researcher, model_family, model_version, product, api, repository, paper, benchmark, license, compute_platform, chip, supplier, investor. Event types for MVP: model_release, model_update, api_launch, open_source_release, paper_release, benchmark_result, funding, researcher_move, chip_supply_change, rumor_detected.
- [ ] **Step 4: Implement `ClaimDraft` / `EventDraft` and promotion helpers.** Do not infer semantics from raw text; inputs are already normalized. `promote_claim` copies evidence IDs and produces revision 1. `canonicalize_event` produces revision 1 with explicit status and canonical IDs.
- [ ] **Step 5: Run** targeted test and expect PASS.
- [ ] **Step 6: Run** full AUSI suite.
- [ ] **Step 7: Commit** `feat: add AI industry canonicalization contracts`.

### Task 3: Minimal resource budget, daily selector, and anytime partial batch

**Files:**
- Create: `src/ai_web_research/resource_control/__init__.py`
- Create: `src/ai_web_research/resource_control/models.py`
- Create: `src/ai_web_research/domains/ai_industry/daily.py`
- Create: `tests/ausi/test_ai_daily_selection.py`

**Interfaces:**
- Consumes: `CanonicalClaim`, `CanonicalEvent`, `KnowledgeState`.
- Produces: `ResearchBudget`, `AnytimeStatus`, `DailySelectionPolicy`, `DailyEventInput`, `DailyBatch`, `select_daily_batch`.

- [ ] **Step 1: Write failing tests.** Main brief allows only `confirmed` events whose factual claims are `well_supported` or `confirmed`; rumor candidates appear only in `what_to_watch` when enabled and remain labeled unverified; score ordering is deterministic; `max_selected_events` truncation returns `complete=False`, `stop_reason='budget_exhausted'`, and `open_event_ids`.
- [ ] **Step 2: Run** targeted tests and verify RED.
- [ ] **Step 3: Implement minimal `ResearchBudget`.** Fields: `max_selected_events`, `max_watch_events`; non-negative validation only. This is intentionally smaller than B07 full multi-resource vector.
- [ ] **Step 4: Implement selector score** exactly as spec: `0.35*importance + 0.25*freshness + 0.20*audience_relevance + 0.20*confidence`; sort by descending score then stable `event_id` tie-break.
- [ ] **Step 5: Implement `DailyBatch`.** Required fields: `batch_id`, `knowledge_state_id`, `selected_event_ids`, `watch_event_ids`, `complete`, `stop_reason`, `open_event_ids`, `generated_at`.
- [ ] **Step 6: Run** targeted tests and expect PASS.
- [ ] **Step 7: Run** full AUSI suite.
- [ ] **Step 8: Commit** `feat: add bounded AI daily event selector`.

### Task 4: Traceable machine + Traditional Chinese projections and correction registry

**Files:**
- Create: `src/ai_web_research/projection/__init__.py`
- Create: `src/ai_web_research/projection/models.py`
- Create: `src/ai_web_research/projection/daily.py`
- Create: `src/ai_web_research/projection/registry.py`
- Create: `tests/ausi/test_ai_daily_projection.py`

**Interfaces:**
- Consumes: `DailyBatch`, `CanonicalEvent`, `CanonicalClaim`, `KnowledgeState`.
- Produces: `ProjectionUnit`, `ProjectionArtifact`, `CorrectionImpact`, `render_machine_daily`, `render_zh_hant_daily`, `ArtifactRegistry`.

- [ ] **Step 1: Write failing tests.** Every factual projection unit maps to claim/event IDs; all artifacts retain one batch `KnowledgeStateID`; confirmed → `已確認`, well-supported → `多方支持`, unverified rumor watch → `尚未確認`, disputed → `資訊有爭議`; projection never upgrades state; artifact registry can return all artifacts affected by a claim ID.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement projection models.** `ProjectionUnit`: `unit_id`, `text`, `claim_ids`, `event_ids`, `status_label`. `ProjectionArtifact`: `artifact_id`, `channel`, `knowledge_state_id`, `revision`, `units`, `generated_at`, `metadata`. `CorrectionImpact`: `claim_id`, `artifact_ids`.
- [ ] **Step 4: Implement deterministic machine renderer.** Return JSON-serializable dict containing batch/state IDs, event IDs, watch IDs, completeness and per-unit lineage.
- [ ] **Step 5: Implement deterministic zh-Hant renderer.** One line/segment per canonical event, using the first eligible claim statement and explicit status label. Watchlist gets a separate `值得追蹤（尚未確認）` section.
- [ ] **Step 6: Implement in-memory `ArtifactRegistry`.** Register artifacts; index claim/event dependencies; `affected_by_claim(claim_id)` returns stable artifact IDs. No external media mutation in MVP.
- [ ] **Step 7: Run** targeted tests and expect PASS.
- [ ] **Step 8: Run** full AUSI suite.
- [ ] **Step 9: Commit** `feat: add traceable AI daily projections`.

### Task 5: End-to-end Series B AI Daily fixture and correction propagation

**Files:**
- Create: `tests/ausi/fixtures/ai_daily_release_scenario.py`
- Create: `tests/ausi/test_ai_daily_mvp_e2e.py`
- Create: `src/ai_web_research/domains/ai_industry/mvp.py`

**Interfaces:**
- Consumes: Task 1–4 contracts.
- Produces: `AIDailyMVPResult`, `build_ai_daily_mvp`.

- [ ] **Step 1: Write failing E2E test fixture.** Scenario: one sensor report, one official blog, one official repository, two syndicated media references collapsed to one independent root family, release confirmed, license initially wrong then corrected, API availability not operationally confirmed, and a budget allowing only one main event.
- [ ] **Step 2: Assert AC-01/02.** Every projected factual claim has evidence IDs, and fixture evidence IDs point to synthetic source locators stored in fixture metadata.
- [ ] **Step 3: Assert AC-03.** Four observed source mentions for release produce `independent_root_count=2` (official blog + official repository; syndicated media collapsed).
- [ ] **Step 4: Assert AC-04/05.** Rumor/watch status remains unverified and one stable `model_release` event ID is used across duplicate observations.
- [ ] **Step 5: Assert AC-06/10.** Every zh-Hant segment maps to claim/event IDs and machine + zh-Hant artifacts share one knowledge state ID.
- [ ] **Step 6: Assert AC-07.** Append license claim revision 2 as `superseded` / corrected state and verify artifact registry locates the original artifact by claim ID.
- [ ] **Step 7: Assert AC-08.** Selector returns usable partial batch with `budget_exhausted` when more canonical events exist than budget.
- [ ] **Step 8: Assert AC-09.** Simulate upstream failure by never inserting a failed candidate; compare store counts before/after and prove canonical claims/events are unchanged.
- [ ] **Step 9: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_ai_daily_mvp_e2e.py -q` and verify RED before `mvp.py` exists.
- [ ] **Step 10: Implement `build_ai_daily_mvp`.** Accept already canonicalized fixture inputs, persist claims/events/state, select batch, render machine + zh-Hant artifacts, register artifacts, return all objects. Do not call a network provider.
- [ ] **Step 11: Run** targeted E2E and expect PASS.
- [ ] **Step 12: Run** all AUSI tests and `python -m compileall -q src/ai_web_research tests/ausi`.
- [ ] **Step 13: Commit** `feat: complete AI Daily canonical vertical slice`.

### Task 6: Documentation, branch verification, and pull request

**Files:**
- Create: `docs/AI_DAILY_MVP_v0.1.md`
- Modify: `README.md` only with a short pointer if needed.

**Interfaces:**
- Produces: reviewer-ready branch and PR stacked on PR #1.

- [ ] **Step 1: Document the exact MVP boundary.** State that the slice begins from trusted/canonical evidence inputs and deliberately does not claim a general live web-search provider. Explain how this stacks on PR #1.
- [ ] **Step 2: Document acceptance results** AC-01..AC-10 with exact test names.
- [ ] **Step 3: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi -q` if a runnable checkout is available. If sandbox cannot materialize the complete repository, run the locally reconstructed targeted/new suite and state the limitation exactly; do not claim legacy tests passed.
- [ ] **Step 4: Run** `python -m compileall -q src/ai_web_research tests/ausi` on the available source set.
- [ ] **Step 5: Compare** `integration/ausi-runtime-core-v0.1...integration/ai-daily-mvp-v0.1`; verify no `src/crawler/*` or `src/ai_web_research/domains/patents/*` changes.
- [ ] **Step 6: Open stacked PR** targeting `integration/ausi-runtime-core-v0.1`, titled `feat: add Series B AI Daily canonical MVP v0.1`, with scope, tests, limitations, and next slice (live general discovery provider / full temporal modes).
