# Omphalos / AUSI Runtime v0.6 — Evidence / Provenance Closure Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.6 — Evidence / Provenance Closure

## Canonical result

v0.6 closes the evidence path without collapsing retrieval, anchoring, semantic support, or source independence into one status.

```text
DiscoveryCandidate
↓ acquisition / fetch
AcquiredAsset
↓ extraction
CandidateEvidence
↓ ANCHOR + SOURCE_IDENTITY verification
VerifiedEvidence
↓ SourceFamilyResolution
EvidenceProvenance
↓ SEMANTIC_SUPPORT verification
ClaimEvidenceRelation
↓ independent-root assessment
CLAIM_LINKED / CORROBORATED / CONTESTED
```

Permanent boundaries:

```text
Retrieved != Verified
Citation != Support
QuoteMatch != SemanticSupport
ProviderGrounding != VerifiedEvidence
LLM recall != external evidence
```

## Evidence promotion is not claim support

`EvidencePromotionPolicy` defines the requirements for promoting an existing `CandidateEvidence` record into `VerifiedEvidence`.

Default v0.6 promotion requires:

```text
CandidateEvidence
+ source_type != llm_recall
+ anchor exists
+ ANCHOR PASS
+ source identity exists
+ SOURCE_IDENTITY PASS
```

Optional policy can additionally require:

```text
FIXITY PASS
```

The result means:

> the evidence object passed the declared evidence-verification boundary.

It does **not** mean:

> the evidence semantically supports a claim.

`SEMANTIC_SUPPORT` is intentionally not part of the default evidence-promotion gate.

## Claim-link gate

A `ClaimEvidenceRelation` can be created only when a `VerificationResult` satisfies all of:

```text
dimension == SEMANTIC_SUPPORT
decision == PASS
verification.evidence_ref == VerifiedEvidence.evidence_id
verification.claim_ref == target claim
```

Therefore:

```text
ANCHOR PASS
≠
SUPPORTS
```

and:

```text
provider citation / grounding
≠
SUPPORTS
```

Supported relation types are explicit:

```text
SUPPORTS
CONTRADICTS
QUALIFIES
BACKGROUND
```

## Provider-grounding boundary

A model-native/search `DiscoveryCandidate` remains discovery-only.

The v0.6 E2E passes a Gemini-like grounded search candidate directly to the promotion gate and verifies:

```text
NOT_CANDIDATE_EVIDENCE
```

No search rank, snippet, provider citation, or grounded synthesis bypasses acquisition/extraction/verification.

## Provenance / independent-root boundary

`EvidenceProvenance` bridges `VerifiedEvidence` into the existing `SourceFamilyResolution`.

Collapsing source-family relations remain:

```text
SYNDICATED_FROM
MIRRORS
DERIVED_FROM
TRANSLATED_FROM
SAME_ORIGIN_FAMILY
```

Non-collapsing relations include:

```text
CITES
LINKS_TO
```

Consequences:

```text
official source
+ mirror
+ syndicated copy
= one independent root
```

while:

```text
source A CITES source B
≠ same origin family
```

Unknown provenance does not manufacture independence:

```text
independent_root_ref = unresolved:<source>
root_resolved = false
```

Unresolved roots do not count toward corroboration.

## Claim evidence assessment

`assess_claim_evidence(...)` uses resolved independent roots, not raw citation count or evidence-object count.

Reference behavior:

```text
support source A
+ mirror of A
→ 1 independent support root
→ CLAIM_LINKED
```

Then:

```text
+ independent support source B
→ 2 independent support roots
→ CORROBORATED
```

Then:

```text
+ independent semantic contradiction source C
→ CONTESTED
```

Contradiction is explicit evidence state, not silently averaged away.

## Policy / usage provenance

Every `VerifiedEvidence` retains:

```text
usage_envelope_id
```

and `EvidenceClosureRuntime` requires the referenced `UsageEnvelope` to already exist in `TrustedDataStore`.

The closure Runtime does not grant permissions or reinterpret Policy decisions.

It only preserves the acquisition-policy lineage downstream.

## Fail-closed provenance closure

`EvidenceClosureRuntime` requires source-identity verification.

A custom promotion policy with:

```text
require_source_identity = false
```

is rejected before verification/ledger/evidence side effects.

This prevents:

```text
promote evidence
→ later discover provenance cannot be resolved
```

from creating partial closure state.

## EvidenceClosureStore persistence extension

v0.6 keeps the existing `TrustedDataStore` storage core unchanged and adds `EvidenceClosureStore(TrustedDataStore)`. The extension shares the exact same SQLite connection/database and adds only:

```text
verification_results
verified_evidence
evidence_provenance
claim_evidence_relations
```

Existing TrustedDataStore tables are left intact; no destructive migration or base-store API expansion is required.

New closure records are immutable/conflict-safe:

```text
same ID + identical payload
→ idempotent replay

same ID + changed payload
→ TrustedStoreConflict
```

`TrustedExecutionRuntime` now persists the ANCHOR `VerificationResult` objects it already generated through `EvidenceClosureStore(self.store)` before recording the corresponding ledger events.

## Append-only closure ledger

New observable event types include:

```text
VERIFICATION_RECORDED
EVIDENCE_PROMOTED
PROVENANCE_ATTACHED
CLAIM_EVIDENCE_LINKED
CLAIM_CORROBORATED
CLAIM_CONTESTED
GAP_PROJECTED
```

There is no evidence-ledger update path.

Closure produces history; it does not rewrite prior evidence events.

## Evidence closure gaps

v0.6 adds:

```text
UNVERIFIED_SEMANTIC_SUPPORT
UNRESOLVED_PROVENANCE
```

and reuses:

```text
UNRESOLVED_CONTRADICTION
```

Examples:

```text
VerifiedEvidence
+ claim requested
+ no semantic verification
→ UNVERIFIED_SEMANTIC_SUPPORT
```

```text
source family/root unresolved
→ UNRESOLVED_PROVENANCE
```

```text
verified contradiction exists
→ UNRESOLVED_CONTRADICTION
```

## E2E acceptance path

The canonical E2E proves:

```text
model-native DiscoveryCandidate
→ cannot promote

AcquiredAsset
→ CandidateEvidence
→ quote / ANCHOR PASS

ANCHOR PASS only
→ not claim support

+ SOURCE_IDENTITY PASS
→ VerifiedEvidence

+ SourceFamilyResolution
→ EvidenceProvenance

+ SEMANTIC_SUPPORT PASS
→ ClaimEvidenceRelation

source A + mirror A
→ 1 independent root

+ source B
→ CORROBORATED

+ contradiction source C
→ CONTESTED
```

UsageEnvelope/provenance/relation records survive persistence/reload and ledger sequence remains append-only.

## Fresh exact-source reconstructed verification

Final verification included the current-master exact `source_graph/models.py`, `source_graph/family.py`, and `test_source_family.py` blobs as reconstructed base support.

```text
v0.6 targeted:
43 passed in 0.20s

reconstructed AUSI suite:
231 passed in 0.50s

compileall:
exit 0

evidence boundary / secret / CoT schema scan:
PASS
```

The native source-family verification is therefore part of the final v0.6 targeted gate rather than being inferred from the new bridge tests alone.

## Verification limitation

The workspace is still reconstructed/materialized rather than a complete clone of current master.

Current-master base modules needed by the new closure tests were materialized exactly where practical, but:

```text
231 passed
```

must not be relabeled as a fresh run of every current repository or historical legacy crawler test.

## Scope boundary

v0.6 does not add or modify:

```text
Provider selection
Search Methods
Autonomous Planner semantics
Stopping semantics
crawler implementation
```

It closes the evidence/provenance layer only.

## Handoff

Next canonical milestone:

```text
v0.7 — Search Receipt / Experience Learning
```

v0.7 should turn observable execution history into a Search Experience Dataset, including:

```text
method success by task class
provider success by method
gap-resolution yield
evidence yield
cost efficiency
latency efficiency
failure rates
```

while preserving:

```text
SearchReceipt != ChainOfThought
Learning != SelfAuthorization
```
