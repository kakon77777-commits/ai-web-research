# Omphalos v0.2 — Provider State & Dynamic Routing Checkpoint

**Date:** 2026-09-03  
**Status:** Implementation / verification checkpoint  
**Roadmap milestone:** v0.2

## Goal

Prove the Provider Replaceability Principle at runtime:

```text
same Search Method
+ changing ProviderState
→ different eligible MethodBinding
```

without changing Search Method identity and without allowing routing to become authorization.

## Runtime path

```text
Search Method
↓
ProviderRegistrySnapshot
+
ProviderStateSnapshot
+
RoutingPolicy
↓
BindingSelector
↓
RoutingDecision
↓
PolicyEvaluator
↓
AuthorizedAction / rejection
↓
ExecutionRuntime
↓
Search Receipt
```

## Critical boundary

```text
Routing != Authorization
```

`ProviderState.policy_freshness = FRESH` means only that the runtime has a sufficiently fresh routing-side policy state signal. It does **not** grant permission.

The selected action must still pass the normal policy path:

```text
RoutingDecision
→ PolicyEvaluator
→ ALLOW / ALLOW_WITH_OBLIGATIONS / DENY / UNKNOWN / REVIEW
```

Therefore:

```text
FRESH routing policy state != ALLOW
Past successful execution != current authorization
```

## ProviderState v0.2

State is exact to:

```text
(provider_id, provider_version, surface_id)
```

Routing-relevant fields:

```text
availability
healthy
credential_available
quota_remaining
quota_reset_at
estimated_cost
estimated_latency_ms
policy_freshness
runtime_capabilities
model_available
last_checked_at
reason_codes
metadata
```

Credential handling is presence-only:

```text
credential value
→ deployment helper
→ bool credential_available
```

Credential values are never part of ProviderState or RoutingDecision.

ProviderState also fails closed on obvious secret-bearing metadata keys such as API-key/token/private-key/password fields.

## Deterministic BindingSelector

Hard rejection reasons include:

```text
MISSING_PROVIDER_STATE
PROVIDER_UNAVAILABLE
PROVIDER_DEGRADED
PROVIDER_AVAILABILITY_UNKNOWN
PROVIDER_UNHEALTHY
PROVIDER_HEALTH_UNKNOWN
CREDENTIAL_UNAVAILABLE
CREDENTIAL_UNKNOWN
MODEL_UNAVAILABLE
MODEL_AVAILABILITY_UNKNOWN
QUOTA_EXHAUSTED
POLICY_STATE_STALE
POLICY_STATE_REVIEW_REQUIRED
POLICY_STATE_UNKNOWN
RUNTIME_CAPABILITY_MISSING
COST_LIMIT_EXCEEDED
LATENCY_LIMIT_EXCEEDED
```

Selection order is deterministic:

```text
explicit binding preference
→ provider preference
→ topology preference
→ availability class
→ estimated cost
→ estimated latency
→ provider id
→ surface id
→ binding id
```

## Provider substitution pressure test

The v0.2 acceptance pressure test holds the Method constant:

```text
method.lexical_search@1.0.0
```

and changes only ProviderState:

```text
1. Gemini Vertex
   healthy + credential + quota
   → selected

2. Gemini Vertex
   quota = 0
   → QUOTA_EXHAUSTED
   → Gemini AI Studio selected

3. Gemini AI Studio
   credential unavailable
   → CREDENTIAL_UNAVAILABLE
   → Grok Web selected

4. Grok Web
   provider unavailable
   → PROVIDER_UNAVAILABLE
   → Brave selected

5. Brave
   provider unavailable
   → NO_ELIGIBLE_BINDING
```

At every stage:

```text
method_ref == method.lexical_search@1.0.0
```

This is the first direct runtime proof of:

```text
Method Stable
Provider Replaceable
```

## Search Receipt integration

`SearchActionReceipt` schema remains backward compatible.

Routing is persisted in:

```text
SearchActionReceipt.metadata["routing"]
```

for success, policy rejection, and provider execution failure.

The routing record includes:

```text
method ref
routing policy id
provider registry snapshot id
provider state snapshot id
selected binding/provider/surface
candidate eligibility
candidate reject reason codes
```

It does not include:

```text
raw credentials
credential values
hidden reasoning
chain of thought
arbitrary ProviderState metadata
```

## Fresh verification

Exact source synchronized with the GitHub v0.2 feature branch was freshly verified in the reconstructed AUSI workspace:

```text
v0.2 targeted suite:
29 passed

reconstructed AUSI suite:
118 passed

compileall:
exit 0

runtime secret / CoT schema scan:
PASS
```

## Verification limitation

The local workspace is a reconstructed/materialized AUSI workspace rather than a complete clone of the current GitHub repository. Therefore `118 passed` is **not** relabeled as a fresh run of every test currently present on master or of the historical legacy crawler suite.

GitHub source-identity verification is performed separately by matching exact blobs for the v0.2 changed source/test files and by comparing the feature branch against current master.

## v0.2 non-goals

Not part of this milestone:

- learned routing policy;
- autonomous planner rewrite;
- Search Method Corpus;
- billing/quota provider polling services;
- new search providers;
- retry/backoff redesign;
- Economic Research Domain Pack;
- Meteorological Research Domain Pack.

## Roadmap handoff

After v0.2 is merged and checkpointed, the next canonical milestone is:

```text
v0.3 — Search Method Corpus + Core Method Set
```

Provider additions and domain research features should not preempt that milestone unless required to repair a v0.2/v0.3 blocker.
