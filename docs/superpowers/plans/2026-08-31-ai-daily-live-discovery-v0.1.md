# AI Daily Live Discovery + Source Lineage v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing AI Daily canonical MVP with a real general-search provider contract, provider-neutral discovery candidates, reverse-source planning, deterministic source-family collapse, and runtime-derived independent-root counts.

**Architecture:** Stack on `integration/ai-daily-mvp-v0.1`; do not reimplement AUSI core. Add one Brave Search provider adapter under `providers/`, a small domain-independent `source_graph/` package, and a thin AI Daily live-discovery helper that feeds the existing `ClaimDraft -> promote_claim -> DailyBatch -> Projection` path. Search results remain discovery-only; only fetched/anchored evidence can support canonical claims.

**Tech Stack:** Python >=3.11, stdlib dataclasses/enum/hashlib, existing `httpx`, existing AUSI provider/execution/policy contracts, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-ai-daily-live-discovery-design.md`

## Global Constraints

- Base on `integration/ai-daily-mvp-v0.1` @ `a22d82e6027e39ce5472f83e9687430c498d06a4`.
- Do not modify legacy `src/crawler/*` behavior.
- Do not modify Patent domain behavior.
- Do not add runtime dependencies.
- `Method != Provider`.
- `SearchResult != Evidence`.
- `MentionCount != IndependentEvidenceCount`.
- Search snippets are discovery metadata only and never become canonical evidence.
- Brave credential exists only in execution context; never store or log the secret.
- Missing predecessor is a legal state; never fabricate source lineage.
- Provider rank is not evidence of source dependency.
- Existing AI Daily projection/status semantics must remain unchanged.
- All default tests are network-free and deterministic.

---

### Task 1: Brave Search provider contract and adapter

**Files:**
- Create: `src/ai_web_research/providers/brave_search.py`
- Create: `tests/ausi/test_brave_search_provider.py`
- Modify: `src/ai_web_research/providers/__init__.py` only if exports are needed.

**Interfaces:**
- Consumes: `AuthorizedAction`, `ExecutionContext`, `ProviderObservation`, `ProviderRegistry`, `MethodRegistrySnapshot`, `SourcePolicyProfile`.
- Produces: `BraveSearchAdapter`, `BraveSearchAdapterError`, `BraveSearchCredentialError`, `register_brave_search_provider`, `register_brave_search_policy`, `register_brave_search_adapter`, `brave_search_policy_profile`.

- [ ] **Step 1: Write failing provider tests.** Cover exact provider/binding IDs, missing credential failure before transport, `X-Subscription-Token` header, `q/count/country/search_lang` params, deterministic candidate normalization, and `evidence_role='discovery_only'`.
- [ ] **Step 2: Run** `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ausi/test_brave_search_provider.py -q`; verify RED because module does not exist.
- [ ] **Step 3: Implement constants and registration.** Use `provider.brave_search@1.0.0`, `surface.brave_search.web`, adapter `brave_search.web@1.0.0`, binding `binding.lexical_search.brave_search.v1`; bind existing `method.lexical_search@1.0.0` and capability `capability.lexical`.
- [ ] **Step 4: Implement execution-time credential boundary.** Read `context.services['brave_search_api_key']`; reject missing/blank credential before `_get()`; never include token in observation metadata/diagnostics.
- [ ] **Step 5: Implement injectable HTTP call.** Use `context.services['brave_search_http_client']` when supplied; otherwise lazily construct `httpx.AsyncClient`; GET `https://api.search.brave.com/res/v1/web/search`; clamp `count` to 1..20.
- [ ] **Step 6: Normalize `web.results`.** Each result becomes `ArtifactRef(ArtifactKind.CANDIDATE, ...)` with `url`, `title`, `description`, `provider_rank`, `source_type='brave_web_search_result'`, `external_source=True`, `evidence_role='discovery_only'`.
- [ ] **Step 7: Implement conservative policy profile.** Grant only documented `AUTOMATED_QUERY`; record auth requirement `X-Subscription-Token`, documented endpoint, and current 50 req/s product capacity as provider metadata/constraint; do not assert persistent redistribution rights.
- [ ] **Step 8: Run** targeted tests and expect PASS.
- [ ] **Step 9: Commit** `feat: add Brave general search provider`.

### Task 2: Provider-neutral discovery candidate normalization

**Files:**
- Create: `src/ai_web_research/discovery/__init__.py`
- Create: `src/ai_web_research/discovery/models.py`
- Create: `src/ai_web_research/discovery/normalize.py`
- Create: `tests/ausi/test_discovery_candidates.py`

**Interfaces:**
- Consumes: `ProviderObservation`, `ArtifactRef`.
- Produces: `DiscoveryCandidate`, `DiscoveryBatch`, `normalize_discovery_observation`.

- [ ] **Step 1: Write failing tests.** Candidate IDs must be stable per provider artifact, URL required, rank preserved, search snippets remain metadata, duplicate candidate URLs fold to first provider rank while retaining `artifact_ids`, and non-candidate artifacts are ignored.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement frozen `DiscoveryCandidate`.** Fields: `candidate_id`, `url`, `title`, `snippet`, `provider_id`, `surface_id`, `provider_rank`, `artifact_ids`, `metadata`.
- [ ] **Step 4: Implement `DiscoveryBatch`.** Fields: `observation_id`, `query`, `candidates`, `provider_id`, `occurred_at`.
- [ ] **Step 5: Implement normalization.** Fold exact normalized URLs deterministically; preserve first rank and all contributing artifact IDs; never create evidence objects.
- [ ] **Step 6: Run** targeted tests and expect PASS.
- [ ] **Step 7: Commit** `feat: normalize provider discovery candidates`.

### Task 3: Source graph and deterministic source-family resolver

**Files:**
- Create: `src/ai_web_research/source_graph/__init__.py`
- Create: `src/ai_web_research/source_graph/models.py`
- Create: `src/ai_web_research/source_graph/family.py`
- Create: `tests/ausi/test_source_family.py`

**Interfaces:**
- Produces: `SourceRelationType`, `RelationInferenceType`, `SourceNode`, `SourceRelation`, `SourceFamily`, `SourceFamilyResolution`, `resolve_source_families`.

- [ ] **Step 1: Write failing tests.** `syndicated_from`, `mirrors`, `derived_from`, `translated_from`, `same_origin_family` collapse; `cites/links_to/mentions` do not collapse; cycles are deterministic and unresolved; two independent roots remain two families; `independent_root_count(source_ids)` returns family cardinality rather than mention count.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement source models.** `SourceNode`: `source_id`, `url`, `canonical_url`, `published_at`, `observed_at`, `owner_hint`, `content_hash`, `metadata`. `SourceRelation`: IDs, type, confidence, inference type, signals.
- [ ] **Step 4: Implement deterministic family resolution.** Collapse only dependency relation types; use directed predecessor edges to choose roots; timestamp then lexical tie-break; cycles produce `root_resolved=False` and deterministic family ID.
- [ ] **Step 5: Implement `SourceFamilyResolution.independent_root_count(source_ids)`** by unique family IDs of known sources; unknown source IDs each count as distinct unresolved roots rather than disappearing.
- [ ] **Step 6: Run** targeted tests and expect PASS.
- [ ] **Step 7: Commit** `feat: add source-family dependency resolver`.

### Task 4: Reverse-source trace planning and explicit-edge materialization

**Files:**
- Create: `src/ai_web_research/source_graph/trace.py`
- Create: `tests/ausi/test_reverse_source_trace.py`

**Interfaces:**
- Consumes: `DiscoveryCandidate`, `SourceNode`, `SourceRelation`.
- Produces: `SourceTraceSignals`, `TraceActionKind`, `TraceAction`, `ReverseTracePlan`, `plan_reverse_trace`, `materialize_explicit_trace_edges`.

- [ ] **Step 1: Write failing tests.** Explicit attributed URLs produce direct predecessor actions; quoted phrases produce exact-quote search actions; attribution entity + claim keywords produces entity search; no signals returns unresolved plan; search result rank alone produces no dependency edge; candidate URL matching an explicit attributed URL produces a `derived_from`/`cites` edge with explicit signal and confidence 1.0.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement `SourceTraceSignals`.** Fields: `attributed_source_urls`, `attribution_entities`, `quoted_phrases`, `claim_keywords`.
- [ ] **Step 4: Implement provider-neutral trace actions.** Kinds: `DIRECT_PREDECESSOR`, `EXACT_QUOTE_SEARCH`, `ENTITY_SEARCH`; search actions carry plain query strings and expected signal, not provider IDs.
- [ ] **Step 5: Implement exact materialization only.** Create dependency relation only when candidate URL matches an explicit attributed URL; quote/entity search results remain predecessor candidates until separately verified. No semantic guess in this slice.
- [ ] **Step 6: Run** targeted tests and expect PASS.
- [ ] **Step 7: Commit** `feat: add reverse source trace planner`.

### Task 5: Automatic independent-root attachment for AI claims

**Files:**
- Create: `src/ai_web_research/domains/ai_industry/source_independence.py`
- Create: `tests/ausi/test_ai_claim_source_independence.py`

**Interfaces:**
- Consumes: existing `ClaimDraft`, `SourceFamilyResolution`.
- Produces: `attach_independent_root_count`.

- [ ] **Step 1: Write failing tests.** Four source mentions in two resolved families yield `independent_root_count=2`; unresolved source IDs are counted independently; original `ClaimDraft` is not mutated; resulting draft passes existing `promote_claim()` unchanged.
- [ ] **Step 2: Run** targeted test and verify RED.
- [ ] **Step 3: Implement helper using `dataclasses.replace`.** Inputs: draft, `evidence_source_ids`, family resolution. Output: copy with computed count.
- [ ] **Step 4: Run** targeted test and expect PASS.
- [ ] **Step 5: Run existing AI Daily canonicalization/selection/projection tests** to ensure no behavior drift.
- [ ] **Step 6: Commit** `feat: derive AI claim independence from source graph`.

### Task 6: Live-discovery AI Daily E2E fixture and optional smoke command

**Files:**
- Create: `src/ai_web_research/domains/ai_industry/live_discovery.py`
- Create: `tests/ausi/fixtures/ai_daily_live_discovery_scenario.py`
- Create: `tests/ausi/test_ai_daily_live_discovery_e2e.py`
- Create: `scripts/verify_brave_search_provider.py`

**Interfaces:**
- Consumes: Brave adapter observation, discovery normalization, trace planner, family resolver, existing AI Daily canonical/projection contracts.
- Produces: `AIDailyDiscoveryResult`, `build_ai_daily_from_discovery`.

- [ ] **Step 1: Write failing E2E test.** Synthetic Brave response has official blog, official repo, Media A, Media B; Media A explicitly attributes official blog; Media B is syndicated from Media A; repository remains independent.
- [ ] **Step 2: Assert discovery semantics.** Search artifacts are discovery-only and their snippets never appear in canonical evidence IDs.
- [ ] **Step 3: Assert trace/family semantics.** Reverse trace creates only evidence-backed explicit dependency edges; family resolver produces two independent roots.
- [ ] **Step 4: Assert canonical integration.** Release claim is promoted with runtime-computed `independent_root_count=2`; existing event ID/status rules remain unchanged.
- [ ] **Step 5: Assert projection compatibility.** Machine + zh-Hant artifacts share one state ID and status labels are unchanged from PR #2.
- [ ] **Step 6: Run** targeted E2E and verify RED before `live_discovery.py` exists.
- [ ] **Step 7: Implement `build_ai_daily_from_discovery`.** Accept provider observation + already fetched/anchored canonical evidence + source nodes/trace signals; normalize discovery, resolve explicit source dependencies, attach independent-root count, call existing promotion/MVP projection functions. No network inside this helper.
- [ ] **Step 8: Implement optional Brave smoke script.** If `BRAVE_SEARCH_API_KEY` missing, print `SKIPPED_NO_CREDENTIAL` and exit 0; if present, execute one low-count query through `BraveSearchAdapter`, verify candidate URL presence, and never print the key.
- [ ] **Step 9: Run** targeted E2E and expect PASS.
- [ ] **Step 10: Run all new-slice tests plus existing PR #2 AI Daily tests.** Then compile `src/ai_web_research` and `tests/ausi` on the available source set.
- [ ] **Step 11: Commit** `feat: connect AI Daily discovery to source lineage`.

### Task 7: Documentation, verification, and stacked PR

**Files:**
- Create: `docs/AI_DAILY_LIVE_DISCOVERY_v0.1.md`

**Interfaces:**
- Produces: reviewer-ready stacked branch and PR.

- [ ] **Step 1: Document provider boundary.** State Brave endpoint/auth mechanism, credential absence/presence, and that search snippets are discovery-only.
- [ ] **Step 2: Document LD-01..LD-10 results** with exact test names.
- [ ] **Step 3: Fresh verification.** Run all new tests and existing AI Daily tests; run `compileall`. If full repo cannot be cloned, disclose exactly as PR #2 did.
- [ ] **Step 4: Optional live check.** Run `scripts/verify_brave_search_provider.py`; report either actual live success or exactly `SKIPPED_NO_CREDENTIAL`; never call a mock result “live”.
- [ ] **Step 5: Compare** `integration/ai-daily-mvp-v0.1...integration/ai-daily-live-discovery-v0.1`; verify no `src/crawler/*` or Patent changes.
- [ ] **Step 6: Open stacked PR** targeting `integration/ai-daily-mvp-v0.1`, title `feat: add AI Daily live discovery and source lineage v0.1`, with provider docs, tests, credential limitation, and next slice (fetched-page signal extraction / broader reverse-trace heuristics / B04 modes).
