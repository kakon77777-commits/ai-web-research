# AUSI Runtime Core v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first canonical AUSI runtime slice: framework-independent core contracts, method/provider registries and bindings, Search Graph validation, and a deterministic planner without changing legacy crawler behavior.

**Architecture:** Add `src/ai_web_research/` alongside the existing `src/crawler/`. The new runtime is stdlib-only (`dataclasses`, `enum.StrEnum`, `typing`) and treats legacy code as future provider adapters rather than rewriting it. Registry snapshots are immutable within an epoch; provider capability matching is not sufficient without an explicit MethodBinding; plans are validated before any policy or execution layer.

**Tech Stack:** Python >=3.11, dataclasses, enum.StrEnum, typing.Protocol, pytest.

**Spec:** AUSI WP-01 and WP-02 canonical architecture/contracts discussed and approved before this implementation slice.

## Global Constraints

- Do not modify legacy crawler behavior in this slice.
- Do not add runtime dependencies.
- `Method != Provider`, `Provider != Surface`, `CapabilityMatch != BindingExists`.
- `Plan != Authorization`; policy/evidence implementation is out of scope for this slice.
- Registry entries with the same `(id, version)` may be re-registered only when payloads are identical.
- Registry snapshots are immutable objects and are the planning input.
- Search plans must reject implicit cycles; loops require an explicit bounded `LoopNode`.
- Provider observations are not evidence.
- Keep the existing `crawler` console entry point working.

---

### Task 1: Canonical core contracts and packaging

**Files:**
- Create: `src/ai_web_research/__init__.py`
- Create: `src/ai_web_research/core/__init__.py`
- Create: `src/ai_web_research/core/types.py`
- Create: `tests/ausi/test_core_types.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `VersionRef`, `ArtifactKind`, `ArtifactRef`, `SearchIntent`, `RiskClass`, `SearchTask`, `ActionKind`, `SearchAction`, `StopAction`.

- [ ] **Step 1: Write failing tests** for frozen/hashable `VersionRef`, task construction, and artifact/action serialization-friendly values.
- [ ] **Step 2: Run** `pytest tests/ausi/test_core_types.py -q` and verify import failure because `ai_web_research` does not exist.
- [ ] **Step 3: Implement minimal core dataclasses/enums** using Python stdlib only.
- [ ] **Step 4: Update Hatch wheel packages** to include both `src/crawler` and `src/ai_web_research`.
- [ ] **Step 5: Run** `pytest tests/ausi/test_core_types.py -q` and expect PASS.
- [ ] **Step 6: Commit** `feat: add AUSI core contracts`.

### Task 2: SearchMethodSpec and immutable method registry

**Files:**
- Create: `src/ai_web_research/methods/__init__.py`
- Create: `src/ai_web_research/methods/spec.py`
- Create: `src/ai_web_research/methods/registry.py`
- Create: `tests/ausi/test_method_registry.py`

**Interfaces:**
- Consumes: `VersionRef`, `ArtifactKind`.
- Produces: `MethodGoal`, `RepresentationKind`, `SearchDirection`, `InteractionMode`, `EvidenceEffect`, `MethodAvailability`, `ContractSpec`, `FailureSpec`, `SearchMethodSpec`, `SearchMethodRegistry`, `MethodRegistrySnapshot`, `RegistryVersionConflict`.

- [ ] **Step 1: Write failing tests** proving identical re-registration is idempotent, conflicting same-version payload raises `RegistryVersionConflict`, latest version resolves, and snapshots do not change after later registrations.
- [ ] **Step 2: Run** `pytest tests/ausi/test_method_registry.py -q` and verify RED.
- [ ] **Step 3: Implement minimal method spec and registry** with deterministic tuple ordering in snapshots.
- [ ] **Step 4: Run** `pytest tests/ausi/test_method_registry.py -q` and expect PASS.
- [ ] **Step 5: Commit** `feat: add AUSI method registry`.

### Task 3: Provider specs, surfaces, capabilities, and MethodBinding

**Files:**
- Create: `src/ai_web_research/providers/__init__.py`
- Create: `src/ai_web_research/providers/spec.py`
- Create: `src/ai_web_research/providers/registry.py`
- Create: `tests/ausi/test_provider_registry.py`

**Interfaces:**
- Consumes: `VersionRef`, `SearchMethodSpec`.
- Produces: `ProviderKind`, `SurfaceKind`, `ProviderSurface`, `ProviderSpec`, `MethodBinding`, `ProviderRegistry`, `ProviderRegistrySnapshot`, `BindingValidationError`.

- [ ] **Step 1: Write failing tests** proving capability-compatible surfaces still require an explicit enabled binding, missing surfaces are rejected, and stale capability/binding mismatches are rejected.
- [ ] **Step 2: Run** `pytest tests/ausi/test_provider_registry.py -q` and verify RED.
- [ ] **Step 3: Implement provider/surface/binding registry** with explicit `validate_binding(method_registry, binding)`.
- [ ] **Step 4: Run** `pytest tests/ausi/test_provider_registry.py -q` and expect PASS.
- [ ] **Step 5: Commit** `feat: add AUSI provider bindings`.

### Task 4: Search Graph AST and PlanValidator

**Files:**
- Create: `src/ai_web_research/planning/__init__.py`
- Create: `src/ai_web_research/planning/graph.py`
- Create: `src/ai_web_research/planning/validator.py`
- Create: `tests/ausi/test_plan_validator.py`

**Interfaces:**
- Consumes: `SearchAction`, method/provider registry snapshots.
- Produces: `NodeKind`, `EdgeKind`, `ActionNode`, `StopNode`, `JoinNode`, `BranchNode`, `LoopNode`, `PlanEdge`, `SearchPlan`, `ValidationIssue`, `PlanValidationResult`, `PlanValidator`.

- [ ] **Step 1: Write failing tests** for valid sequential plans, unknown bindings, artifact type mismatch, implicit cycles, and unbounded loops.
- [ ] **Step 2: Run** `pytest tests/ausi/test_plan_validator.py -q` and verify RED.
- [ ] **Step 3: Implement the minimal AST and validation pipeline**: structure, registry resolution, availability, binding/capability check, artifact compatibility, cycle and loop checks.
- [ ] **Step 4: Run** `pytest tests/ausi/test_plan_validator.py -q` and expect PASS.
- [ ] **Step 5: Commit** `feat: add AUSI search plan validator`.

### Task 5: Built-in specs and deterministic planner baseline

**Files:**
- Create: `src/ai_web_research/methods/builtin.py`
- Create: `src/ai_web_research/providers/builtin.py`
- Create: `src/ai_web_research/planning/planner.py`
- Create: `tests/ausi/test_deterministic_planner.py`

**Interfaces:**
- Consumes: task, registry snapshots, SearchAction/SearchPlan.
- Produces: `register_builtin_methods`, `register_builtin_providers`, `DeterministicPlanner`.

- [ ] **Step 1: Write failing tests** that register the current capability status: query divergence, identity search, lexical search, crawl discovery, fetch document, LLM recall, candidate evidence extraction as available; semantic/citation/version search unavailable; counter-evidence partial.
- [ ] **Step 2: Write failing planner test** for a `RESOLVE_IDENTITY` task selecting the local-corpus identity-search binding and producing a validator-clean one-action plan.
- [ ] **Step 3: Run** `pytest tests/ausi/test_deterministic_planner.py -q` and verify RED.
- [ ] **Step 4: Implement built-in specs and the smallest deterministic planner rule** for `RESOLVE_IDENTITY`; unsupported intents raise a typed `PlanningError` rather than guessing.
- [ ] **Step 5: Run** all AUSI tests: `pytest tests/ausi -q` and expect PASS.
- [ ] **Step 6: Commit** `feat: add AUSI deterministic planner baseline`.

### Task 6: Slice-level verification and handoff

**Files:**
- Modify: `README.md` only if needed to add a short non-disruptive note that the AUSI runtime core is being introduced alongside the legacy crawler.

**Interfaces:**
- Produces: a self-contained branch suitable for review before legacy adapters are added.

- [ ] **Step 1: Run** `pytest tests/ausi -q`.
- [ ] **Step 2: Run** the existing repository test suite in an environment with the full checkout: `pytest -q`; record the result in the PR. If the execution environment cannot obtain the full checkout, state that limitation explicitly and do not claim the legacy suite passed.
- [ ] **Step 3: Inspect the diff** and confirm no legacy crawler source behavior changed.
- [ ] **Step 4: Create a PR** titled `feat: introduce AUSI runtime core contracts v0.1` with implemented scope, tests run, limitations, and next slice (legacy adapters).
