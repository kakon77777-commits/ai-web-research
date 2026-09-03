# Omphalos / AUSI Runtime v0.4 — Autonomous Search Planner v1 Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.4 — Autonomous Search Planner v1

## Canonical result

v0.4 establishes the first provider-neutral autonomous search-planning boundary:

```text
SearchTask + SearchState + Open Gaps + Budget
+ MethodCorpusSnapshot + MethodRegistrySnapshot
+ ProviderRegistrySnapshot + ProviderStateSnapshot
↓
SearchStrategyProposal
↓
Method lifecycle/runtime/input gate
↓
BindingSelector / ProviderState routing
↓
SearchPlan
↓
PlanValidator
↓
PolicyEvaluator (still outside planner and authoritative)
```

The permanent boundary remains:

```text
AI proposes
Runtime validates
Policy authorizes
```

Planner output is never authorization.

## New runtime

```text
src/ai_web_research/planning/autonomous_models.py
src/ai_web_research/planning/proposal.py
src/ai_web_research/planning/autonomous.py
src/ai_web_research/planning/receipt.py
```

No v0.2 routing runtime file is modified.

## Provider-neutral proposal contract

`SearchStrategyProposal` contains:

```text
proposal_id
task_id
method-level steps
objectives
candidate method IDs
bounded replan condition
reason codes
```

It deliberately contains no:

```text
provider ID
surface ID
binding ID
credential
provider request body
policy authorization
hidden reasoning
```

A future model/agent proposer can emit this contract without receiving authority to choose secrets or bypass Runtime gates.

## Deterministic baseline proposer

`RuleProposalSource` is the v0.4 reference proposer. It maps observable task/gap state to provider-neutral method candidates.

Examples:

```text
RESEARCH
→ method.lexical_search
+ optional method.query_divergence

identity_unresolved
→ method.identity_search

candidate_acquisition
→ method.fetch_document

evidence_missing + DOCUMENT present
→ method.extract_candidate_evidence

counter_evidence
→ method.counter_evidence_search
→ method.lexical_search fallback candidate
```

The deterministic proposer is a baseline/reference implementation, not a claim that rule planning is the final AI strategy model.

## Method maturity gate

By default:

```text
VALIDATED / EXECUTABLE
→ eligible for compilation

EXPERIMENTAL
→ blocked unless PlanningPolicy.allow_experimental = true

DOCUMENTED
→ knowledge only, never compiled

DEPRECATED
→ blocked
```

A lifecycle-eligible method still needs:

```text
registered SearchMethodSpec
runtime availability != unavailable/deprecated
compatible input artifact
eligible Provider binding under ProviderState
```

This preserves the v0.3 distinction:

```text
Known Method != Executable Method
```

## Method substitution

The proposal can list ordered candidate methods for one objective.

Acceptance example:

```text
counter_evidence gap
↓
method.counter_evidence_search
    EXPERIMENTAL, disallowed by default
↓
method.lexical_search
    execution-ready
↓
compile lexical action
```

This makes method substitution explicit without silently promoting the experimental method.

## Provider fallback

v0.4 does not add a new routing API.

For a compiled method:

```text
BindingSelector
→ primary RoutingDecision
→ read eligible non-primary candidate binding IDs
→ second BindingSelector call with fallback preference order
```

Both primary and fallback retain the exact same `method_ref`.

Example:

```text
method.lexical_search
→ provider A binding
→ BranchNode: failed_or_empty
    TRUE  → provider B binding, same method
    FALSE → JoinNode
```

`max_provider_fallbacks` is a global plan cap.

Routing remains distinct from authorization.

## Graph capabilities proven in v0.4

The compiler can emit:

```text
parallel ActionNode entries
BranchNode provider fallback
JoinNode convergence
one bounded LoopNode for replan
StopNode for epoch boundary / no-capability state
```

The loop is explicitly bounded by both:

```text
PlanningBudget.max_loop_iterations
SearchStrategyProposal.max_replans
```

No implicit/unbounded cycle is introduced; existing `PlanValidator` remains authoritative.

## Budget behavior

Typed `PlanningBudget` controls:

```text
max_actions
max_parallel_branches
max_loop_iterations
max_provider_fallbacks
```

Task and runtime state limits are intersected deterministically.

Invalid/non-positive budget values never expand runtime limits.

## Receipt boundary

`planning_receipt_metadata(...)` persists only observable planning facts:

```text
proposal ID
plan ID
planner ID/version
method-corpus snapshot
provider-state snapshot
selected/skipped method IDs
skip reason codes
open gap refs
objectives
budget
sanitized routing summaries
```

It excludes:

```text
credentials
raw ProviderState metadata
Policy ALLOW/DENY authority
hidden reasoning
Chain-of-Thought
```

The metadata can be placed under the existing `SearchReceipt.metadata["planning"]` without a SQLite schema migration.

## E2E acceptance path

The v0.4 pressure test is:

```text
FALSIFY task
+ counter_evidence gap
↓
provider-neutral proposal
↓
method.counter_evidence_search rejected by default experimental gate
↓
method.lexical_search substituted
↓
ProviderState routing selects neutral provider A
↓
provider fallback branch selects neutral provider B with same method
↓
Join
↓
bounded open-gaps replan loop
↓
PlanValidator PASS
↓
receipt-safe planning metadata persisted and loaded
```

## Verification

Fresh local reconstructed verification before GitHub synchronization:

```text
v0.4 targeted: 38 passed
reconstructed AUSI: 170 passed
compileall: exit 0
planner secret / CoT schema scan: PASS
```

Exact GitHub-source verification is performed again after synchronization before the PR is declared review-ready.

## Scope boundaries / limitations

v0.4 intentionally does not:

- call an external LLM to generate the proposal; callers may supply a typed `SearchStrategyProposal`, while `RuleProposalSource` is the deterministic baseline;
- implement the seven documented-only v1 core methods;
- add a Provider;
- change Policy authorization semantics;
- define final research stop/completeness semantics — v0.5 owns stopping, coverage, saturation, and uncertainty;
- implement arbitrary proposal DAG dependencies; v0.4 supports independent parallel steps, fallback branch, join, and one bounded replan loop.

## Handoff

Next canonical milestone:

```text
v0.5 — Stopping / Coverage / Saturation
```

v0.5 should consume the now-available planning state and formalize:

```text
StopCondition
SearchBudget
CoverageState
SaturationState
UncertaintyState
marginal evidence gain
explicit stop reason
```

without weakening:

```text
NotFound != False
Saturation != CompleteRecall
```
