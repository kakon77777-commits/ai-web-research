# Omphalos / AUSI Runtime v0.8 — Evaluation / Benchmark Suite Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.8 — Evaluation / Benchmark Suite

## Canonical result

v0.8 adds a deterministic paired-case evaluation harness and a clearly labeled synthetic reference suite.

```text
BenchmarkSpec
+ BenchmarkDataset
→ paired-case validation
→ BenchmarkRunner
→ VariantSummary
→ baseline comparisons
→ BenchmarkReport
→ ReproducibilityManifest
→ machine-readable suite artifacts
```

The v0.8 reference suite covers all five canonical benchmark families:

```text
Provider substitution
Method diversity
Adaptive planning
Provenance independence
Replay / reproducibility
```

## Critical scientific boundary

The bundled reference suite is **synthetic**.

It validates the benchmark protocol, metric semantics, comparison mechanics, source-independence accounting, and reproducibility behavior.

It does **not** demonstrate live-Web superiority, empirical Provider superiority, or production research quality superiority.

Real Brave / Grok / Gemini / Crossref / EPO or other live runs must be captured as separate empirical datasets and evaluated with the same harness.

## Fair-comparison rules

Every compared variant must cover the same case IDs.

```text
baseline:  case A / B / C
candidate: case A / C
→ INVALID
```

Duplicate `(variant_id, case_id)` observations are rejected.

Unknown metric values remain `None` and are excluded from known-value denominators rather than silently becoming zero.

Every metric declares one of:

```text
HIGHER_IS_BETTER
LOWER_IS_BETTER
NEUTRAL
```

Every aggregate exposes:

```text
value
known_count
total_count
```

## Canonical metrics

The harness supports:

```text
success_rate
provider_failure_rate
avg_candidate_yield
avg_verified_evidence_yield
avg_independent_root_yield
avg_gap_reduction
avg_cost
avg_latency_ms
avg_actions
avg_replans
source_overcount
source_independence_ratio
```

`success_rate` means full `SUCCESS` trial status; `PARTIAL` is not silently counted as full success.

`provider_failure_rate` is a trial-level terminal/unrecovered Provider failure indicator, not a count of every internal fallback attempt.

## Provider substitution synthetic reference

```text
single_provider:
  success_rate                 = 0.3333
  provider_failure_rate        = 0.6667
  verified_evidence_yield      = 0.6667
  avg_cost                     = 0.4333
  avg_latency_ms               = 36.6667

dynamic_substitution:
  success_rate                 = 1.0000
  provider_failure_rate        = 0.0000
  verified_evidence_yield      = 2.0000
  avg_cost                     = 1.1667
  avg_latency_ms               = 96.6667
```

The synthetic fixture therefore demonstrates a resilience tradeoff:

```text
higher continuity / evidence yield
but
higher fallback cost / latency
```

It does not claim substitution is always cheaper or faster.

## Method diversity synthetic reference

```text
lexical_only:
  success_rate                 = 0.0000
  candidate_yield              = 6.3333
  verified_evidence_yield      = 1.0000
  gap_reduction                = 0.3333
  actions                      = 2.0000
  cost                         = 1.0000

multi_method:
  success_rate                 = 1.0000
  candidate_yield              = 8.3333
  verified_evidence_yield      = 3.3333
  gap_reduction                = 2.3333
  actions                      = 4.3333
  cost                         = 1.5667
```

The synthetic fixture explicitly preserves the quality/resource tradeoff:

```text
more methods
→ more evidence / gap resolution
→ also more actions / cost
```

## Adaptive planning synthetic reference

```text
fixed_plan:
  success_rate                 = 0.3333
  gap_reduction                = 0.6667
  actions                      = 6.0000
  cost                         = 2.2333
  latency_ms                   = 230.0000

gap_adaptive:
  success_rate                 = 1.0000
  gap_reduction                = 2.0000
  actions                      = 3.3333
  cost                         = 1.5333
  latency_ms                   = 153.3333
```

This is a deterministic mechanism fixture, not a claim that every adaptive plan will dominate every fixed plan in production.

## Provenance independence synthetic reference

```text
raw_mentions:
  source_overcount             = 2.6667
  source_independence_ratio    = 0.5222
  independent_roots            = 2.3333

family_aware:
  source_overcount             = 0.0000
  source_independence_ratio    = 1.0000
  independent_roots            = 2.3333
```

The independent-root total does not artificially increase.

The improvement is in accounting quality:

```text
mirror / syndicated copies
≠ independent roots

CITES
≠ same origin family
```

## Replay / reproducibility reference

The replay benchmark uses equal observable outcomes for canonical and reordered input variants.

```text
success_rate = 1.0 / 1.0
avg_cost     = 1.0 / 1.0
comparison deltas = 0
```

The stronger replay condition is content-addressed identity:

```text
same spec
+ same observations in different order
→ same spec snapshot
→ same dataset snapshot
→ same benchmark report ID
→ same suite report ID
```

Changing a dataset observation or runner/spec semantics invalidates the manifest replay gate.

## Reproducibility identities

Canonical fixture SHA-256:

```text
80126f5955f738dd4f20c8d7e8e6b344df6e16e401bc921b1c4f9cc610515d19
```

Suite report ID:

```text
benchmark-suite-report:fd41c90c2a5e03955b8caed648756eb14fad07fea9b1099533f6d06d8e243fa5
```

Suite manifest ID:

```text
benchmark-suite-manifest:b55b115a579d04bdeca039ca47d044215c44abdfcde44ea44536dab2644b4ca7
```

Machine-readable canonical artifacts:

```text
benchmarks/omphalos-v0.8-reference-suite.json
benchmarks/artifacts/omphalos-v0.8-reference-report.json
benchmarks/artifacts/omphalos-v0.8-reference-manifest.json
```

The repository test suite regenerates the report and manifest and requires byte-exact text equality.

## Scope boundary

v0.8 adds only the evaluation harness, benchmark fixtures, benchmark tests, artifacts, and documentation.

It does not change:

```text
Provider adapters
Routing
Policy authorization
Search Methods
Autonomous Planner semantics
Stopping semantics
Evidence / Provenance semantics
Experience Learning semantics
crawler implementation
```

## Fresh reconstructed verification

```text
v0.8 targeted:
38 passed in 0.08s

v0.7 + v0.8 reconstructed compatibility suite:
60 passed in 0.11s

compileall:
exit 0

machine-readable artifact exact regeneration:
PASS

evaluation secret / CoT schema scan:
PASS

synthetic-vs-live claim gate:
PASS
```

Verification limitation:

The local workspace is a targeted reconstructed compatibility workspace rather than a complete fresh clone/execution of every current-master or historical crawler test.

The bundled reference suite performs no live network calls. Its numbers remain synthetic mechanism/measurement fixtures and must not be relabeled as empirical Provider performance.

## Handoff

Next canonical milestone:

```text
v0.9 — API Freeze / Hardening / Release Candidate
```

v0.9 should stop adding major Runtime behavior and focus on:

```text
public API/schema freeze
error taxonomy
migration rules
packaging
clean install
security / secret checks
documentation
reference workflows
reproducible RC package
```
