# Omphalos v1 API Stability and Migration Policy

**Public API Version: `1.0`**  
**Final Package: `1.0.0`**  
**Historical Release Candidate: `1.0.0rc1`**

## Public facade

`omphalos` is the stable public facade.

`ai_web_research` remains the implementation package and is intentionally not renamed in a big-bang migration. Existing internal imports may continue to work, but v1 compatibility guarantees are defined by the `omphalos` facade and the machine-readable public API manifest.

Frozen v1 contracts include at least `SearchTask`, `SearchState`, `SearchAction`, `SearchMethodSpec`, `ProviderSpec`, `ProviderState`, `MethodBinding`, `SearchPlan`, `AuthorizedAction`, `ProviderObservation`, `CandidateEvidence`, `VerifiedEvidence`, `EvidenceProvenance`, `GapProjection`, `SearchReceipt`, and `SearchActionReceipt`.

## RC-to-final freeze

The historical RC API artifact is retained byte-for-byte. The final `1.0.0` API artifact must regenerate from the final facade and must contain the same public contract descriptors and public API version as the RC artifact. Package version promotion alone does not authorize schema drift.

## Semantic Versioning

Package releases follow Semantic Versioning.

- Patch releases may fix defects without breaking frozen public contracts.
- Minor releases may add backward-compatible public contracts or optional fields only when compatibility is preserved.
- Breaking changes to the v1 public facade require a major-version migration.
- Historical RC artifacts remain historical evidence and are not rewritten after final promotion.

## Machine-readable freeze

`release/omphalos-v1.0.0-public-api.json` records the final package identity plus the frozen source contract, dataclass field order, frozen status, and enum values for the public facade. `release/omphalos-v1.0.0rc1-public-api.json` remains the byte-identical RC snapshot.

## Deprecation policy

A public v1 symbol must not disappear silently. A planned deprecation must be documented, provide a migration path and replacement where applicable, preserve compatibility for an appropriate release window, and must not reinterpret stored receipt/evidence meaning retroactively.

## Migration rules

Migration is additive whenever possible. Stored artifacts are versioned by their own schema/contract identities. New code must not silently reinterpret historical `SearchReceipt`, evidence, benchmark, or Experience records.

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
