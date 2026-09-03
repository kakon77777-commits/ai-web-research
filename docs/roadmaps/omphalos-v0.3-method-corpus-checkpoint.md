# Omphalos / AUSI Runtime v0.3 — Search Method Corpus Checkpoint

**Date:** 2026-09-03  
**Milestone:** v0.3 — Search Method Corpus + Core Method Set

## Canonical result

v0.3 separates two axes that must never be conflated:

```text
MethodAvailability
= runtime execution availability of a SearchMethodSpec

MethodLifecycle
= research/maturity state of a method in the Search Method Corpus
```

A method can therefore legitimately be:

```text
DOCUMENTED + UNAVAILABLE
EXPERIMENTAL + PARTIAL
EXECUTABLE + AVAILABLE
VALIDATED + AVAILABLE
```

This prevents Omphalos from treating a documented research method as an implemented capability.

## Runtime added

```text
src/ai_web_research/methods/corpus.py
src/ai_web_research/methods/corpus_builtin.py
src/ai_web_research/methods/coverage.py
src/ai_web_research/methods/corpus_validation.py
```

Key contracts:

```text
MethodLifecycle
MethodReference
MethodCorpusEntry
SearchMethodCorpus
MethodCorpusSnapshot
MethodCoverageReport
MethodCorpusValidationIssue
```

## Corpus v0.1 state

Initial corpus:

```text
34 total methods
23 DOCUMENTED
1  EXPERIMENTAL
5  EXECUTABLE
5  VALIDATED
0  DEPRECATED
```

The corpus includes:

- classic query/search forms;
- iterative/exploratory search methods;
- citation and systematic-search methods;
- falsification/counter-evidence methods;
- machine/runtime methods already used by Omphalos;
- Patent Intelligence domain methods.

Human-readable companion:

`docs/methods/search-method-corpus-v0.1.md`

## v1 Core Method Target

The v1 core target is provider-neutral and domain-neutral:

```text
method.lexical_search
method.exact_search
method.query_divergence
method.identity_search
method.entity_search
method.classification_search
method.backward_citation
method.forward_citation
method.counter_evidence_search
method.temporal_version_search
method.relation_resolve
method.fetch_document
method.extract_candidate_evidence
```

Current v0.3 readiness:

```text
Documented:       13 / 13 = 100%
Execution-ready:   5 / 13
Experimental:      1 / 13
Documented-only:   7 / 13
Missing corpus:    0 / 13
```

Execution-ready core methods:

```text
method.lexical_search
method.query_divergence
method.identity_search
method.fetch_document
method.extract_candidate_evidence
```

Experimental:

```text
method.counter_evidence_search
```

Documented-only core gaps:

```text
method.exact_search
method.entity_search
method.classification_search
method.backward_citation
method.forward_citation
method.temporal_version_search
method.relation_resolve
```

These gaps are intentional and visible. v0.3 does not implement them merely to improve a coverage number.

## Domain boundary

The Patent Domain Pack already has validated/executable methods such as:

```text
method.patent.classification_search
method.patent.family_resolve
method.patent.claims_fetch
```

They remain domain methods and do not masquerade as generic core methods.

## Registry consistency gate

`validate_corpus_against_registry(...)` enforces:

```text
EXECUTABLE / VALIDATED
→ spec_ref required
→ spec identity must match method identity
→ referenced SearchMethodSpec must exist
→ runtime availability cannot be UNAVAILABLE / DEPRECATED
```

`DOCUMENTED / EXPERIMENTAL` methods may exist without executable specs.

## Handoff

v0.3 is the method-space inventory/maturity layer. It is not the autonomous-planning milestone.

Next canonical milestone:

```text
v0.4 — Autonomous Search Planner v1
```

v0.4 should consume:

```text
SearchTask
SearchState
EvidenceState
GapState
ProviderState
MethodRegistrySnapshot
MethodCorpusSnapshot
MethodCoverage / method lifecycle information
Budget
```

and propose multi-method plans while leaving validation and authorization authoritative in their existing runtime layers.

New Providers, Economic/Meteorological Domain Packs, and unrelated method implementations should not preempt v0.4 unless they repair a roadmap blocker.
