# Omphalos / AUSI Runtime v0.7 — Search Receipt / Experience Learning Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.7 — Search Receipt / Experience Learning

## Canonical result

v0.7 converts observable execution history into a deterministic, replayable Search Experience Dataset and preference-only Planner Prior.

```text
SearchReceipt / SearchActionReceipt
+ ExperienceYieldFact
↓
SearchExperienceRecord
↓
SearchExperienceDataset
↓
Method / Provider / Gap / Evidence / Cost / Latency metrics
↓
PlannerPriorSnapshot
```

Permanent boundaries:

```text
SearchReceipt != ChainOfThought
Learning != SelfAuthorization
```

## Experience derivation

`SearchExperienceRecord` preserves only bounded observable facts:

```text
task / epoch / task class
method / provider / surface / binding
execution outcome
result / artifact count
candidate gain
verified evidence gain
independent-root gain
gaps resolved / opened
resolved gap types
normalized USD cost when explicitly present
latency
policy decision / reason codes for audit
source receipt/action-receipt refs
observable fact refs
```

Arbitrary SearchReceipt metadata is not copied into the Experience record.

Unknown yield is represented as `None`, not zero.

```text
unknown evidence gain != zero evidence gain
```

Yield facts bind to immutable `action_receipt_id`, not reusable `action_id`.

## Outcome semantics

```text
SUCCEEDED + result_count > 0 → SUCCESS
SUCCEEDED + result_count == 0 → EMPTY
PARTIAL                      → PARTIAL
provider execution failure   → FAILED
DENY / UNKNOWN               → BLOCKED
REVIEW                       → REVIEW
```

Policy control outcomes are explicitly separate from provider execution failure:

```text
DENY / UNKNOWN / REVIEW != ProviderFailure
```

## Anti-double-count discipline

Dataset construction rejects:

```text
duplicate receipt_id
duplicate action_receipt_id across receipts
```

This prevents replay/revision inputs from silently inflating success rates.

## Deterministic dataset

`SearchExperienceDataset` is sorted and content-addressed.

```text
derivation_version = 0.7.0
snapshot_id = hash(version + canonical records)
```

Input receipt ordering does not affect snapshot identity.

## Metrics

v0.7 exposes:

```text
MethodSuccess(method, task_class)
ProviderSuccess(provider, method, task_class)
ExecutionFailureRate
ProviderFailureRate
CandidateYield
VerifiedEvidenceYield
IndependentRootYield
GapResolution(method, gap_type)
CostEfficiency
LatencyEfficiency
```

Unknown measurement values are excluded from their known-value denominator rather than converted into zero.

## Planner Prior

`PlannerPriorSnapshot` is versioned:

```text
prior_version = 0.7.0
```

It contains method and method×provider preference statistics.

Its APIs are intentionally limited to:

```text
rank_methods(caller_supplied_candidates)
rank_providers(method, caller_supplied_candidates)
```

The returned sequence is only a reordering of the supplied candidate set.

Therefore:

```text
historically preferred Provider A
+ Runtime eligibility supplies only Provider B
→ Prior returns only Provider B
```

The Prior cannot reintroduce A, authorize A, create credentials, or bypass Routing / Policy evaluation.

## Additive persistence

`SearchExperienceStore` shares the existing receipt SQLite connection and owns only additive tables:

```text
search_experience_records
experience_dataset_snapshots
planner_prior_snapshots
```

Existing SearchReceiptStore tables/API are not modified.

Same ID + identical payload is idempotent replay; same ID + changed payload raises `ExperienceStoreConflict`.

## Experience Learning Runtime

`ExperienceLearningRuntime.learn(...)` performs:

```text
receipts + contexts
→ dataset
→ immutable records
→ dataset snapshot
→ per-task-class metrics
→ per-task-class Planner Prior
→ immutable prior snapshot
```

Replaying the same exact inputs produces the same dataset/prior identities and does not duplicate history.

## Scope boundary

v0.7 does not modify:

```text
Provider adapters
Routing eligibility
PolicyEvaluator
AuthorizationResult
Autonomous Planner graph semantics
Stopping semantics
Evidence promotion / claim-link semantics
Crawler
```

## Handoff

Next canonical milestone:

```text
v0.8 — Evaluation / Benchmark Suite
```

It should compare:

```text
single-provider vs hybrid provider routing
lexical-only vs method-diverse search
fixed plan vs gap-directed adaptive planner
raw mention count vs independent source roots
replay/reproducibility
```

## Fresh reconstructed verification

```text
v0.7 targeted: 22 passed
compileall: exit 0
```

The local workspace is a targeted reconstructed compatibility workspace using the current SearchReceipt/VersionRef/PolicyDecision/ObservationStatus contracts required by v0.7; it is not claimed as the complete current-master repository suite.
