from __future__ import annotations

from ai_web_research.core.types import VersionRef

from .corpus import (
    MethodCorpusEntry,
    MethodLifecycle,
    MethodReference,
    SearchMethodCorpus,
)


BATES_1989 = MethodReference(
    "ref.bates.1989.berrypicking",
    "Bates, M. J. (1989). The Design of Browsing and Berrypicking Techniques for the Online Search Interface.",
)
MARCHIONINI_2006 = MethodReference(
    "ref.marchionini.2006.exploratory",
    "Marchionini, G. (2006). Exploratory Search: From Finding to Understanding.",
)
PRISMA_S_2021 = MethodReference(
    "ref.prisma-s.2021",
    "Rethlefsen, M. L. et al. (2021). PRISMA-S: an extension to the PRISMA Statement for reporting literature searches in systematic reviews.",
)


def _ref(method_id: str) -> VersionRef:
    return VersionRef(method_id, "1.0.0")


def _entry(
    method_id: str,
    canonical_name: str,
    lifecycle: MethodLifecycle,
    purpose: str,
    *,
    domain: str = "core",
    aliases: tuple[str, ...] = (),
    history: str = "",
    goals: tuple[str, ...] = ("discover",),
    provider_requirements: tuple[str, ...] = (),
    composition_predecessors: tuple[str, ...] = (),
    composition_successors: tuple[str, ...] = (),
    failure_modes: tuple[str, ...] = (),
    references: tuple[MethodReference, ...] = (),
    spec_ref: VersionRef | None = None,
    notes: tuple[str, ...] = (),
) -> MethodCorpusEntry:
    return MethodCorpusEntry(
        method_id=method_id,
        canonical_name=canonical_name,
        lifecycle=lifecycle,
        aliases=aliases,
        domain=domain,
        purpose=purpose,
        history=history,
        goals=goals,
        provider_requirements=provider_requirements,
        composition_predecessors=composition_predecessors,
        composition_successors=composition_successors,
        failure_modes=failure_modes,
        references=references,
        spec_ref=spec_ref,
        notes=notes,
    )


def _entries() -> tuple[MethodCorpusEntry, ...]:
    documented = MethodLifecycle.DOCUMENTED
    executable = MethodLifecycle.EXECUTABLE
    validated = MethodLifecycle.VALIDATED
    experimental = MethodLifecycle.EXPERIMENTAL

    return (
        _entry(
            "method.boolean_search", "Boolean Search", documented,
            "Combine terms with explicit Boolean operators to control recall and precision.",
            history="Classical information-retrieval query formulation.",
            provider_requirements=("capability.boolean_query",),
            composition_successors=("method.exact_search", "method.faceted_search"),
            failure_modes=("operator syntax differs across execution surfaces",),
        ),
        _entry(
            "method.exact_search", "Exact Search", documented,
            "Locate an exact identifier, token, value, or literal expression.",
            aliases=("exact_lookup",),
            goals=("locate",),
            provider_requirements=("capability.exact_match",),
            composition_successors=("method.identity_search", "method.fetch_document"),
            failure_modes=("normalization or version drift hides an exact match",),
        ),
        _entry(
            "method.phrase_search", "Phrase Search", documented,
            "Search for an ordered literal phrase as a unit rather than independent terms.",
            goals=("locate", "narrow"),
            provider_requirements=("capability.phrase_query",),
            composition_successors=("method.counter_evidence_search",),
            failure_modes=("quotation or punctuation normalization prevents matching",),
        ),
        _entry(
            "method.lexical_search", "Lexical Search", validated,
            "Retrieve candidates by lexical query over an external or local corpus.",
            aliases=("keyword_search",),
            provider_requirements=("capability.lexical",),
            composition_predecessors=("method.query_divergence",),
            composition_successors=("method.fetch_document", "method.counter_evidence_search"),
            failure_modes=("vocabulary mismatch", "ranking bias", "query ambiguity"),
            spec_ref=_ref("method.lexical_search"),
            notes=("Validated with multiple replaceable provider bindings in Omphalos v0.2.",),
        ),
        _entry(
            "method.query_expansion", "Query Expansion", documented,
            "Add related terms, aliases, translations, or controlled-vocabulary terms to broaden retrieval.",
            goals=("expand",),
            provider_requirements=("capability.query_transform",),
            composition_successors=("method.lexical_search", "method.semantic_search"),
            failure_modes=("topic drift",),
        ),
        _entry(
            "method.query_divergence", "Query Divergence", executable,
            "Generate deliberately different search branches across semantic, task, source, language, or perspective axes.",
            goals=("expand",),
            provider_requirements=("capability.llm_generate",),
            composition_successors=("method.lexical_search", "method.berrypicking"),
            failure_modes=("branch redundancy", "unbounded expansion"),
            spec_ref=_ref("method.query_divergence"),
        ),
        _entry(
            "method.identity_search", "Identity Search", executable,
            "Search multiple lexical views and fold results that refer to the same canonical identity.",
            aliases=("IPMCS-lite",),
            goals=("locate", "reconcile"),
            provider_requirements=("capability.lexical", "capability.identity_fold"),
            composition_successors=("method.fetch_document",),
            failure_modes=("identity ambiguity", "missing canonical identifiers"),
            spec_ref=_ref("method.identity_search"),
        ),
        _entry(
            "method.entity_search", "Entity Search", documented,
            "Retrieve records by entity names, aliases, identifiers, and typed relations.",
            goals=("locate", "relate"),
            provider_requirements=("capability.entity_query",),
            composition_successors=("method.relation_resolve",),
            failure_modes=("entity collision", "alias ambiguity"),
        ),
        _entry(
            "method.faceted_search", "Faceted Search", documented,
            "Iteratively narrow a candidate set using structured facets.",
            goals=("narrow",),
            provider_requirements=("capability.facets",),
            composition_predecessors=("method.lexical_search",),
            failure_modes=("facet schema mismatch",),
        ),
        _entry(
            "method.classification_search", "Classification Search", documented,
            "Search through a controlled taxonomy or classification system without binding the method to one domain.",
            goals=("discover", "narrow"),
            provider_requirements=("capability.taxonomy_filter",),
            composition_successors=("method.lexical_search",),
            failure_modes=("classification drift", "incorrect classification symbol"),
        ),
        _entry(
            "method.semantic_search", "Semantic Search", documented,
            "Retrieve candidates by semantic similarity rather than literal lexical overlap.",
            provider_requirements=("capability.semantic",),
            composition_successors=("method.fetch_document",),
            failure_modes=("embedding mismatch", "opaque similarity semantics"),
            spec_ref=_ref("method.semantic_search"),
        ),
        _entry(
            "method.backward_citation", "Backward Citation Search", documented,
            "Follow references from a known work to earlier cited works.",
            goals=("relate", "discover"),
            provider_requirements=("capability.citation_backward",),
            composition_predecessors=("method.fetch_document",),
            composition_successors=("method.snowballing",),
            failure_modes=("incomplete reference metadata",),
            spec_ref=_ref("method.backward_citation"),
        ),
        _entry(
            "method.forward_citation", "Forward Citation Search", documented,
            "Find later works that cite a known work.",
            goals=("relate", "discover"),
            provider_requirements=("capability.citation_forward",),
            composition_successors=("method.snowballing",),
            failure_modes=("citation index coverage gap",),
            spec_ref=_ref("method.forward_citation"),
        ),
        _entry(
            "method.snowballing", "Citation Snowballing", documented,
            "Iteratively combine backward and forward citation chasing to expand a literature set.",
            goals=("expand", "relate"),
            provider_requirements=("capability.citation_backward", "capability.citation_forward"),
            composition_predecessors=("method.backward_citation", "method.forward_citation"),
            composition_successors=("method.systematic_review_search",),
            failure_modes=("citation-network bias", "unbounded iteration"),
            references=(PRISMA_S_2021,),
        ),
        _entry(
            "method.berrypicking", "Berrypicking", documented,
            "Evolve the search query and sources iteratively as newly encountered information changes the information need.",
            goals=("discover", "expand", "reconcile"),
            provider_requirements=("capability.iterative_search",),
            composition_predecessors=("method.lexical_search",),
            composition_successors=("method.query_divergence", "method.lexical_search"),
            failure_modes=("search drift", "non-reproducible branch growth"),
            references=(BATES_1989,),
        ),
        _entry(
            "method.exploratory_search", "Exploratory Search", documented,
            "Use iterative searching for learning, investigation, comparison, and understanding when the target is not fully specified.",
            goals=("discover", "reconcile"),
            provider_requirements=("capability.iterative_search",),
            composition_successors=("method.berrypicking", "method.query_divergence"),
            failure_modes=("goal drift", "premature synthesis"),
            references=(MARCHIONINI_2006,),
        ),
        _entry(
            "method.systematic_review_search", "Systematic Review Search", documented,
            "Run a reproducible multi-source literature-search protocol with explicit queries, dates, sources, and supplementary citation searching.",
            goals=("discover", "verify"),
            provider_requirements=("capability.reproducible_query",),
            composition_successors=("method.backward_citation", "method.forward_citation", "method.snowballing"),
            failure_modes=("database coverage bias", "poorly reported search strategy"),
            references=(PRISMA_S_2021,),
        ),
        _entry(
            "method.counter_evidence_search", "Counter-Evidence Search", experimental,
            "Search specifically for evidence that could contradict, narrow, or qualify the current claim.",
            goals=("falsify", "verify"),
            provider_requirements=("capability.counter_search",),
            composition_predecessors=("method.lexical_search",),
            composition_successors=("method.fetch_document",),
            failure_modes=("confirmation-biased query generation",),
            spec_ref=_ref("method.counter_evidence_search"),
        ),
        _entry(
            "method.prior_art_search", "Prior-Art Search", documented,
            "Search patent and non-patent literature before a cutoff using lexical, classification, family, citation, and chronology methods.",
            domain="patent_intelligence",
            goals=("discover", "verify", "falsify"),
            provider_requirements=("capability.patent_search",),
            composition_successors=("method.patent.classification_search", "method.patent.family_resolve"),
            failure_modes=("family ambiguity", "cutoff leakage", "incomplete jurisdiction coverage"),
        ),
        _entry(
            "method.temporal_version_search", "Temporal / Version Search", documented,
            "Search explicitly across versions, publication states, and time-bounded manifestations.",
            goals=("reconcile", "locate"),
            provider_requirements=("capability.version_search",),
            composition_successors=("method.fetch_document",),
            failure_modes=("version identity ambiguity", "historical availability unknown"),
            spec_ref=_ref("method.temporal_version_search"),
        ),
        _entry(
            "method.graph_search", "Graph Search", documented,
            "Traverse typed relationships between entities, documents, claims, or sources.",
            goals=("relate", "discover"),
            provider_requirements=("capability.graph_query",),
            composition_successors=("method.relation_resolve",),
            failure_modes=("edge semantics mismatch", "cycle explosion"),
        ),
        _entry(
            "method.relation_resolve", "Relation Resolve", documented,
            "Resolve typed relations and origin/family structure without assuming a domain-specific relation system.",
            goals=("relate", "reconcile"),
            provider_requirements=("capability.relation_resolve",),
            failure_modes=("insufficient identity evidence",),
        ),
        _entry(
            "method.cross_language_search", "Cross-Language Search", documented,
            "Search across languages while retaining concept and source identity across translations.",
            goals=("expand", "discover"),
            provider_requirements=("capability.cross_language",),
            composition_successors=("method.identity_search",),
            failure_modes=("translation drift", "language-specific index coverage"),
        ),
        _entry(
            "method.federated_search", "Federated Search", documented,
            "Execute one search intent across multiple heterogeneous retrieval systems and normalize the returned candidate sets.",
            goals=("expand", "discover"),
            provider_requirements=("capability.federation",),
            composition_successors=("method.identity_search",),
            failure_modes=("incomparable ranking semantics", "duplicate candidates"),
        ),
        _entry(
            "method.adversarial_search", "Adversarial Search", documented,
            "Formulate queries and source choices designed to challenge the current hypothesis or search strategy.",
            goals=("falsify", "reconcile"),
            provider_requirements=("capability.query_transform",),
            composition_successors=("method.counter_evidence_search",),
            failure_modes=("manufactured opposition without evidentiary value",),
        ),
        _entry(
            "method.monitoring_search", "Monitoring Search", documented,
            "Repeat a stable or adaptive query over time to detect newly available information or state changes.",
            goals=("monitor",),
            provider_requirements=("capability.scheduled_query",),
            failure_modes=("duplicate alerts", "temporal gaps"),
        ),
        _entry(
            "method.query_reformulation", "Query Reformulation", documented,
            "Rewrite a query after observing retrieval failures, ambiguity, or new vocabulary.",
            goals=("expand", "narrow"),
            provider_requirements=("capability.query_transform",),
            composition_successors=("method.lexical_search",),
            failure_modes=("semantic drift",),
        ),
        _entry(
            "method.crawl_discovery", "Crawl Discovery", executable,
            "Discover same-scope linked resources by bounded crawling.",
            provider_requirements=("capability.crawl_links",),
            composition_successors=("method.fetch_document",),
            failure_modes=("crawl scope explosion", "robots or policy restriction"),
            spec_ref=_ref("method.crawl_discovery"),
        ),
        _entry(
            "method.fetch_document", "Fetch Document", validated,
            "Acquire a candidate or document reference through an authorized fetch binding.",
            goals=("locate",),
            provider_requirements=("capability.fetch_url",),
            composition_predecessors=("method.lexical_search", "method.crawl_discovery"),
            composition_successors=("method.extract_candidate_evidence",),
            failure_modes=("policy rejection", "provider failure", "invalid document"),
            spec_ref=_ref("method.fetch_document"),
        ),
        _entry(
            "method.extract_candidate_evidence", "Extract Candidate Evidence", validated,
            "Extract structured candidate evidence from an acquired document without treating extraction as semantic verification.",
            goals=("verify",),
            provider_requirements=("capability.extract_structured",),
            composition_predecessors=("method.fetch_document",),
            failure_modes=("anchor missing", "schema mismatch"),
            spec_ref=_ref("method.extract_candidate_evidence"),
            notes=("Candidate evidence remains distinct from verified semantic support.",),
        ),
        _entry(
            "method.llm_recall", "LLM Recall", executable,
            "Use model prior knowledge as a bounded fallback candidate-generation method.",
            provider_requirements=("capability.llm_generate",),
            failure_modes=("stale model knowledge", "hallucinated recall"),
            spec_ref=_ref("method.llm_recall"),
            notes=("LLM recall is not external evidence and must never be presented as retrieved source evidence.",),
        ),
        _entry(
            "method.patent.classification_search", "Patent Classification Search", validated,
            "Search patent candidates using versioned patent classification symbols.",
            domain="patent_intelligence",
            goals=("discover", "narrow"),
            provider_requirements=("capability.taxonomy_filter",),
            composition_successors=("method.patent.family_resolve",),
            failure_modes=("classification symbol mismatch",),
            spec_ref=_ref("method.patent.classification_search"),
        ),
        _entry(
            "method.patent.family_resolve", "Patent Family Resolve", validated,
            "Resolve an explicit patent family definition for a known publication identity.",
            domain="patent_intelligence",
            goals=("relate",),
            provider_requirements=("capability.patent_family",),
            failure_modes=("family definition ambiguity",),
            spec_ref=_ref("method.patent.family_resolve"),
            notes=("Current reference implementation resolves INPADOC extended family explicitly.",),
        ),
        _entry(
            "method.patent.claims_fetch", "Patent Claims Fetch", executable,
            "Retrieve machine-readable patent claims for an identified publication.",
            domain="patent_intelligence",
            goals=("verify",),
            provider_requirements=("capability.patent_claims_fulltext",),
            failure_modes=("legal manifestation not verified",),
            spec_ref=_ref("method.patent.claims_fetch"),
            notes=("Retrieval does not by itself establish authoritative legal manifestation.",),
        ),
    )


def register_builtin_method_corpus(corpus: SearchMethodCorpus) -> None:
    for entry in _entries():
        corpus.register(entry)


def build_builtin_method_corpus() -> SearchMethodCorpus:
    corpus = SearchMethodCorpus()
    register_builtin_method_corpus(corpus)
    return corpus
