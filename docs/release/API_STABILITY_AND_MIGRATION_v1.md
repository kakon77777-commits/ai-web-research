# Omphalos v1 API Stability and Migration Policy

**Public API Version: `1.0`**  
**Release Candidate Package: `1.0.0rc1`**

## Public facade

`omphalos` is the stable public facade.

`ai_web_research` remains the implementation package and is intentionally not renamed in a big-bang migration. Existing internal imports may continue to work, but v1 compatibility guarantees are defined by the `omphalos` facade and the machine-readable public API manifest.

Frozen v1 contracts include at least:

- `SearchTask`
- `SearchState`
- `SearchAction`
- `SearchMethodSpec`
- `ProviderSpec`
- `ProviderState`
- `MethodBinding`
- `SearchPlan`
- `AuthorizedAction`
- `ProviderObservation`
- `CandidateEvidence`
- `VerifiedEvidence`
- `EvidenceProvenance`
- `GapProjection`
- `SearchReceipt`
- `SearchActionReceipt`

## Semantic Versioning

Package releases follow Semantic Versioning.

- Patch releases may fix defects without breaking frozen public contracts.
- Minor releases may add backward-compatible public contracts or optional fields only when compatibility is preserved.
- Breaking changes to the v1 public facade require a major-version migration.
- RC releases may still receive blocker fixes before final v1.0, but the objective of v0.9 is API/schema freeze rather than feature growth.

## Machine-readable freeze

`release/omphalos-v1.0.0rc1-public-api.json` records the source contract, dataclass field order, frozen status, and enum values for the public facade. The release gate regenerates this artifact and requires byte-equivalent semantic content.

## Deprecation policy

A public v1 symbol must not disappear silently.

A planned deprecation must:

1. be documented in release notes;
2. provide a migration path;
3. preserve the old symbol for at least one compatible release line where practical;
4. identify the replacement contract;
5. avoid changing stored receipt/evidence meaning retroactively.

## Migration rules

Migration is additive whenever possible.

Stored artifacts are versioned by their own schema/contract identities. New code must not silently reinterpret historical `SearchReceipt`, evidence, benchmark, or Experience records.

When a schema genuinely changes:

```text
old schema
→ explicit migration / adapter
→ new schema
```

not:

```text
old bytes
→ silently treated as new meaning
```

Provider/API churn is handled in adapters/bindings and should not force a new `SearchMethodSpec` identity unless method semantics changed.

## Compatibility invariants

```text
Method != Provider
Provider != Surface
Planning != Authorization
UNKNOWN != ALLOW
Retrieved != Verified
SearchReceipt != ChainOfThought
Learning != SelfAuthorization
```
