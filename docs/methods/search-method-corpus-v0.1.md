# Omphalos Search Method Corpus v0.1

**Milestone:** AUSI Runtime v0.3  
**Date:** 2026-09-03  
**Corpus Snapshot:** `d1036b878ac6f96736fd4be3539c213ce34abbcaae8220773cb27d098d17f696`

## Purpose

This document is the human-readable companion to `src/ai_web_research/methods/corpus_builtin.py`.
It records methods that Omphalos knows about without implying that every documented method is executable.

Canonical distinction:

```text
MethodAvailability = can the current runtime execute this SearchMethodSpec?
MethodLifecycle    = how mature is this method in the Search Method Corpus?
```

Lifecycle states:

- `DOCUMENTED`: method is defined in the corpus; execution is not claimed.
- `EXPERIMENTAL`: partial/provisional implementation or semantics exist; not v1 execution-ready.
- `EXECUTABLE`: a runtime SearchMethodSpec/implementation exists.
- `VALIDATED`: executable method has passed an acceptance/pressure-test boundary.
- `DEPRECATED`: retained for history/compatibility but should not be selected for new work.

## Corpus Summary

- Total entries: **34**
- Documented: **23**
- Experimental: **1**
- Executable: **5**
- Validated: **5**
- Deprecated: **0**

## v1 Core Method Target

- Target methods: **13**
- Documented coverage: **13/13 = 100.0%**
- Execution-ready coverage: **5/13 = 38.5%**

Execution-ready now:

- `method.extract_candidate_evidence`
- `method.fetch_document`
- `method.identity_search`
- `method.lexical_search`
- `method.query_divergence`

Experimental:

- `method.counter_evidence_search`

Documented-only v1 gaps:

- `method.backward_citation`
- `method.classification_search`
- `method.entity_search`
- `method.exact_search`
- `method.forward_citation`
- `method.relation_resolve`
- `method.temporal_version_search`

## Initial Corpus

| Method ID | Lifecycle | Domain | Runtime Spec | Purpose |
| --- | --- | --- | --- | --- |
| `method.adversarial_search` | `documented` | `core` | — | Formulate queries and source choices designed to challenge the current hypothesis or search strategy. |
| `method.backward_citation` | `documented` | `core` | `method.backward_citation@1.0.0` | Follow references from a known work to earlier cited works. |
| `method.berrypicking` | `documented` | `core` | — | Evolve the search query and sources iteratively as newly encountered information changes the information need. |
| `method.boolean_search` | `documented` | `core` | — | Combine terms with explicit Boolean operators to control recall and precision. |
| `method.classification_search` | `documented` | `core` | — | Search through a controlled taxonomy or classification system without binding the method to one domain. |
| `method.counter_evidence_search` | `experimental` | `core` | `method.counter_evidence_search@1.0.0` | Search specifically for evidence that could contradict, narrow, or qualify the current claim. |
| `method.crawl_discovery` | `executable` | `core` | `method.crawl_discovery@1.0.0` | Discover same-scope linked resources by bounded crawling. |
| `method.cross_language_search` | `documented` | `core` | — | Search across languages while retaining concept and source identity across translations. |
| `method.entity_search` | `documented` | `core` | — | Retrieve records by entity names, aliases, identifiers, and typed relations. |
| `method.exact_search` | `documented` | `core` | — | Locate an exact identifier, token, value, or literal expression. |
| `method.exploratory_search` | `documented` | `core` | — | Use iterative searching for learning, investigation, comparison, and understanding when the target is not fully specified. |
| `method.extract_candidate_evidence` | `validated` | `core` | `method.extract_candidate_evidence@1.0.0` | Extract structured candidate evidence from an acquired document without treating extraction as semantic verification. |
| `method.faceted_search` | `documented` | `core` | — | Iteratively narrow a candidate set using structured facets. |
| `method.federated_search` | `documented` | `core` | — | Execute one search intent across multiple heterogeneous retrieval systems and normalize the returned candidate sets. |
| `method.fetch_document` | `validated` | `core` | `method.fetch_document@1.0.0` | Acquire a candidate or document reference through an authorized fetch binding. |
| `method.forward_citation` | `documented` | `core` | `method.forward_citation@1.0.0` | Find later works that cite a known work. |
| `method.graph_search` | `documented` | `core` | — | Traverse typed relationships between entities, documents, claims, or sources. |
| `method.identity_search` | `executable` | `core` | `method.identity_search@1.0.0` | Search multiple lexical views and fold results that refer to the same canonical identity. |
| `method.lexical_search` | `validated` | `core` | `method.lexical_search@1.0.0` | Retrieve candidates by lexical query over an external or local corpus. |
| `method.llm_recall` | `executable` | `core` | `method.llm_recall@1.0.0` | Use model prior knowledge as a bounded fallback candidate-generation method. |
| `method.monitoring_search` | `documented` | `core` | — | Repeat a stable or adaptive query over time to detect newly available information or state changes. |
| `method.patent.claims_fetch` | `executable` | `patent_intelligence` | `method.patent.claims_fetch@1.0.0` | Retrieve machine-readable patent claims for an identified publication. |
| `method.patent.classification_search` | `validated` | `patent_intelligence` | `method.patent.classification_search@1.0.0` | Search patent candidates using versioned patent classification symbols. |
| `method.patent.family_resolve` | `validated` | `patent_intelligence` | `method.patent.family_resolve@1.0.0` | Resolve an explicit patent family definition for a known publication identity. |
| `method.phrase_search` | `documented` | `core` | — | Search for an ordered literal phrase as a unit rather than independent terms. |
| `method.prior_art_search` | `documented` | `patent_intelligence` | — | Search patent and non-patent literature before a cutoff using lexical, classification, family, citation, and chronology methods. |
| `method.query_divergence` | `executable` | `core` | `method.query_divergence@1.0.0` | Generate deliberately different search branches across semantic, task, source, language, or perspective axes. |
| `method.query_expansion` | `documented` | `core` | — | Add related terms, aliases, translations, or controlled-vocabulary terms to broaden retrieval. |
| `method.query_reformulation` | `documented` | `core` | — | Rewrite a query after observing retrieval failures, ambiguity, or new vocabulary. |
| `method.relation_resolve` | `documented` | `core` | — | Resolve typed relations and origin/family structure without assuming a domain-specific relation system. |
| `method.semantic_search` | `documented` | `core` | `method.semantic_search@1.0.0` | Retrieve candidates by semantic similarity rather than literal lexical overlap. |
| `method.snowballing` | `documented` | `core` | — | Iteratively combine backward and forward citation chasing to expand a literature set. |
| `method.systematic_review_search` | `documented` | `core` | — | Run a reproducible multi-source literature-search protocol with explicit queries, dates, sources, and supplementary citation searching. |
| `method.temporal_version_search` | `documented` | `core` | `method.temporal_version_search@1.0.0` | Search explicitly across versions, publication states, and time-bounded manifestations. |

## Canonical Research References in v0.1

- Bates, M. J. (1989). *The Design of Browsing and Berrypicking Techniques for the Online Search Interface*.
- Marchionini, G. (2006). *Exploratory Search: From Finding to Understanding*.
- Rethlefsen, M. L. et al. (2021). *PRISMA-S: an extension to the PRISMA Statement for reporting literature searches in systematic reviews*.

These references seed the corpus; v0.1 is not intended to be an exhaustive bibliography of information-retrieval history.

## Domain Boundary

Patent entries are intentionally domain-scoped:

- `method.patent.classification_search`
- `method.patent.family_resolve`
- `method.patent.claims_fetch`
- `method.prior_art_search`

They do not automatically satisfy generic v1 core targets such as `method.classification_search` or `method.relation_resolve`.

## Governance Rule

A new method should enter the Corpus before it enters the executable registry. Promotion to `EXECUTABLE` or `VALIDATED` requires a versioned `SearchMethodSpec`, runtime implementation/binding, and validation evidence. Provider names belong in bindings/provider metadata, not in method identities.
