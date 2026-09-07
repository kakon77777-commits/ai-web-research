# Omphalos v1 Reference Workflows

These workflows define v1 integration expectations. They are reference paths, not guarantees that a particular Provider is always available.

Permanent evidence/control invariants apply to every workflow:

```text
Retrieved != Verified
Citation != Support
ProviderGrounding != VerifiedEvidence
Saturation != CompleteRecall
UNKNOWN != ALLOW
```

## General Web Research

```text
Research Task
→ Search Method selection
→ provider-neutral Web routing
→ Brave / Grok Web / Gemini or eligible substitute
→ discovery candidates
→ fetch/acquisition
→ evidence verification
→ counter-evidence / gap analysis
→ explicit stop reason
→ Search Receipt
```

The same method may substitute Providers without changing method identity.

## X / Current Discourse Research

```text
Current-discourse task
→ Grok X or another authorized social/current surface
→ Web cross-check
→ discovery-only social candidates
→ fetch primary/independent sources where available
→ source-family / provenance analysis
→ evidence verification
→ gap/stop
```

Social posts and model-native summaries are not automatically verified evidence.

## Academic / NPL Research

```text
Academic/NPL task
→ Crossref / scholarly metadata search
→ identity/version resolution
→ Web or other scholarly discovery
→ backward/forward citation methods when executable
→ acquisition
→ evidence / provenance
→ counter-evidence
→ receipt
```

Metadata discovery and semantic claim support remain separate verification steps.

## Patent Prior-Art Research

```text
Patent task
→ lexical + classification search
→ EPO OPS or eligible patent Provider
→ family / priority resolution
→ claim/full-text acquisition when authorized
→ Crossref NPL search
→ chronology / coverage gaps
→ evidence/provenance
→ explicit REVIEW when legal manifestation remains unverified
```

Patent family identity is explicit. INPADOC extended family and DOCDB simple family must not be silently conflated.

## Stop semantics

Stopping is always scoped to the current methods, Providers, policy state, budget, and coverage requirements. A saturation stop records bounded saturation, not complete recall.
