# Omphalos / AUSI Runtime v0.5 — Stopping / Coverage / Saturation Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.5 — Stopping / Coverage / Saturation

## Canonical result

v0.5 adds a control layer above the v0.4 planner:

```text
Search state / progress
+ SearchBudget
+ CoverageState
+ SaturationState
+ UncertaintyState
↓
StopEvaluator
↓
CONTINUE / REPLAN / STOP / REVIEW
↓
SearchControlRuntime
↓
AutonomousPlannerV1 or explicit StopNode
```

Permanent semantic invariants:

```text
NotFound != False
Saturation != CompleteRecall
```

## Runtime added

```text
src/ai_web_research/stopping/__init__.py
src/ai_web_research/stopping/models.py
src/ai_web_research/stopping/progress.py
src/ai_web_research/stopping/evaluator.py
src/ai_web_research/stopping/control.py
src/ai_web_research/stopping/receipt.py
```

No v0.4 planner source, routing source, Provider adapter, Policy runtime, Evidence runtime, or Search Method implementation is modified.

## Typed control state

Coverage axes:

```text
METHOD
PROVIDER
SOURCE
EVIDENCE
JURISDICTION
LANGUAGE
TEMPORAL
DOMAIN
```

`CoverageState` distinguishes:

```text
open_material_gap_refs == ()
```

from:

```text
material_gap_assessment_complete == true
AND
open_material_gap_refs == ()
```

Only the second can support `NO_MATERIAL_GAP_REMAINS`.

Required coverage targets must be strictly positive; an empty/zero target cannot manufacture completion.

## Search budget

`SearchBudget` tracks:

```text
max_actions / actions_used
max_cost / cost_used
max_elapsed_ms / elapsed_ms
```

Time exhaustion is distinct from action/cost exhaustion:

```text
TIME_LIMIT_REACHED
BUDGET_EXHAUSTED
```

## Saturation

`assess_saturation(...)` uses a bounded recent marginal-gain window.

Example:

```text
recent gains = [0.05, 0.00, 0.02]
threshold = 0.10
→ local saturation = true
```

Its meaning is explicitly:

```text
bounded to current methods/providers/budget
```

There is no `complete_recall` / `recall_complete` field in the runtime schema.

A not-found-only history can contribute to low observed marginal gain, but it cannot create a falsity conclusion.

## StopEvaluator priority

Deterministic priority:

```text
1. HUMAN_REVIEW_REQUIRED
2. POLICY_BLOCKED
3. PROVIDER_UNAVAILABLE
4. TIME_LIMIT_REACHED
5. BUDGET_EXHAUSTED
6. NO_MATERIAL_GAP_REMAINS
7. COVERAGE_TARGET_MET when explicitly terminal by policy
8. SATURATION_REACHED only with required coverage satisfied
9. MARGINAL_GAIN_BELOW_THRESHOLD → REPLAN
10. CONTINUE_SEARCH
```

Important:

```text
low gain + incomplete coverage
→ REPLAN

low gain + satisfied required coverage
+ saturation stop enabled
→ bounded SATURATION_REACHED
```

Therefore low marginal gain alone is not completion.

## SearchControlRuntime

`SearchControlRuntime` gates the existing `AutonomousPlannerV1`.

```text
STOP / REVIEW
→ one-node SearchPlan containing StopNode / StopAction
→ planner is not called

CONTINUE / REPLAN
→ delegate to existing AutonomousPlannerV1
```

The control layer does not call `PolicyEvaluator` and never marks an action authorized.

## Receipt boundary

`stopping_receipt_metadata(...)` records observable control facts:

```text
disposition
stop reason / reason codes
budget usage and limits
coverage measures and gaps
saturation recent gains / scope
uncertainty summary
progress sample count / not-found count
provider availability boolean
policy-blocked boolean
```

It does not serialize:

```text
credentials
raw ProviderState metadata
Policy authorization
hidden reasoning
Chain-of-Thought
complete-recall claims
```

No SearchReceipt SQLite schema migration is required.

## E2E acceptance path

```text
open material gap
+ initial not-found
→ CONTINUE
→ NOT_FOUND_IS_NOT_FALSE

three low-gain epochs
+ required coverage incomplete
→ REPLAN
→ MARGINAL_GAIN_BELOW_THRESHOLD

three low-gain epochs
+ required coverage satisfied
→ STOP
→ SATURATION_REACHED
```

The final saturation SearchReceipt intentionally uses:

```text
SearchReceiptStatus.PARTIAL
stop_reason = SATURATION_REACHED
```

This represents a bounded search stopping decision, not complete world recall.

## Fresh reconstructed verification

```text
v0.5 targeted:
29 passed in 0.13s

reconstructed AUSI suite:
199 passed in 0.38s

compileall:
exit 0

stopping secret / CoT / completeness schema scan:
PASS
```

## Verification limitation

The execution workspace remains reconstructed/materialized rather than a complete current-master clone.

Therefore:

```text
199 passed
```

is the fresh reconstructed AUSI suite available in this environment, not a claim that every historical legacy crawler/current repository test was freshly executed.

## Handoff

Next canonical milestone:

```text
v0.6 — Evidence / Provenance Closure
```

v0.6 should stabilize the complete discovery-to-evidence chain:

```text
Discovery Candidate
→ Fetched Source
→ AcquiredAsset
→ CandidateEvidence
→ EvidenceAnchor
→ Verification
→ Claim relation
→ Corroboration / Contradiction
→ Evidence Ledger
```

while preserving:

```text
Retrieved != Verified
Citation != Support
QuoteMatch != SemanticSupport
ProviderGrounding != VerifiedEvidence
```
