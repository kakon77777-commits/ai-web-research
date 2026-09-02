# Omphalos / AUSI Runtime

> **Omphalos** is the project codename. **AUSI Runtime** (AI-Native Unified Search Intelligence Runtime) is the technical architecture.
>
> The repository name `ai-web-research` is historical and no longer describes the full scope of the system.

**Omphalos is an AI-native search-method runtime.** It is not a search-API aggregator and it is no longer primarily a crawler project. Its goal is to externalize human- and machine-known search methods as typed, composable operators so that AI can select, combine, execute, verify, stop, and eventually learn search strategies across replaceable execution channels.

```text
Task
  ↓
Search Strategy
  ↓
Search Method
  ↓
Provider Binding
  ↓
Authorized Execution
  ↓
Evidence
  ↓
Gap / Replan
  ↓
Search Receipt / Experience
```

The architectural rule is simple:

```text
Search Method ≠ Provider ≠ Surface ≠ Adapter ≠ Credential
```

A Boolean search, citation chase, classification search, counter-evidence search, family resolution, or temporal/version search is a **method**. Brave, Gemini/Google Search, Grok/X Search, Crossref, EPO OPS, a crawler, or a local corpus are **execution channels** that may implement one or more methods.

## Project identity

```text
Codename:
    Omphalos

Technical name:
    AUSI Runtime
    AI-Native Unified Search Intelligence Runtime

Core identity:
    AI-native Search Method Runtime

Legacy repository name:
    ai-web-research
```

The current Python package remains `ai_web_research` for compatibility. A repository rebrand does not require a disruptive package-wide rename.

## Why method-first instead of API-first?

Provider/API availability changes much faster than search methodology.

```text
quota changes
pricing changes
API deprecations
credentials expire
provider outage
policy changes
```

Those should change `ProviderState`, not the meaning of the search method itself.

```text
Method stable
Provider replaceable
API disposable
```

For example, the same high-level Web-discovery method may be bound to a provider-neutral API or a model-native search tool without redefining the method. Conversely, two different patent methods may both use EPO OPS while retaining different search semantics.

## Provider execution topology

Omphalos distinguishes provider **kind** from provider **topology**. These are orthogonal dimensions.

### Model-native

Search is deeply integrated into the model/tool loop.

Examples / intended routes:

- Gemini + Google Search grounding
- Grok + Web Search
- Grok + X Search

### Provider-neutral

The AI runtime retains more direct control over queries and search sequencing.

Current example:

- Brave Search

### Domain-specific

Authoritative or specialized structured data for one professional domain.

Current examples:

- Crossref — scholarly metadata / NPL discovery
- EPO OPS — patent bibliographic, family, classification, full-text and legal-event data

### Local / private

Search without assuming public-cloud egress.

Current examples:

- local corpus
- legacy crawler / browser acquisition
- future private indexes and enterprise stores

This topology is not a quality ranking. It describes execution shape.

## Current deployment direction

The deployment profile can change without changing AUSI semantics.

```text
Google-native grounding     → Gemini / Google Search
X / social discourse        → Grok / X Search
general neutral Web search  → Brave Search
academic / NPL              → Crossref
patent machine data         → EPO OPS
site acquisition            → crawler
existing local knowledge    → local corpus
```

These are bindings, not architectural centers.

## Search-method program

The long-term Omphalos research program is to turn known search methodologies into AI-operable search methods.

Examples include:

- exact / phrase / Boolean search
- lexical and semantic retrieval
- query reformulation / expansion / divergence
- faceted and classification search
- entity / identity search
- graph and relation search
- backward / forward citation chasing
- snowballing and berrypicking
- exploratory search
- systematic-review search
- temporal / version search
- multilingual search
- counter-evidence and qualification search
- patent prior-art / family / claim-oriented search
- monitoring and reopening search

The project does **not** claim that all known search methods are already implemented. The runtime is designed so methods can be formalized, tested, registered, versioned, composed, and gradually promoted from methodology descriptions into executable `SearchMethodSpec` contracts.

## Runtime architecture

The canonical package is organized around explicit boundaries:

```text
src/ai_web_research/
├── methods/       # SearchMethodSpec + method registry
├── providers/     # provider specs, surfaces, bindings, adapters
├── planning/      # search plans / graphs / validators
├── policy/        # authorization and usage envelopes
├── execution/     # authorized execution → observations
├── evidence/      # candidate/verified evidence and provenance
├── gaps/          # evidence/coverage gaps and replanning inputs
├── experience/    # Search Receipts / strategy experience
├── discovery/     # discovery/frontier capabilities
├── knowledge/     # canonical knowledge state
├── projection/    # outward representations / publication views
└── domains/       # domain packs such as Patent Intelligence
```

The original `src/crawler/` package remains as a compatibility/capability layer while validated behavior is wrapped into the canonical runtime.

## Core invariants

```text
Method ≠ Provider
Provider ≠ Surface
Spec ≠ Implementation
Planning ≠ Authorization
Planner ≠ Executor
UNKNOWN ≠ ALLOW
Retrieved ≠ Verified
Citation ≠ Support
Not Found ≠ False
Search Receipt ≠ Chain-of-Thought
Learning ≠ Self-Authorization
```

These are architecture constraints, not optional prompting conventions.

## Existing implementation highlights

The repository currently includes, among other pieces:

- deterministic, resumable crawler with robots/sitemap/rate-limit/SSRF handling;
- query divergence and legacy model-recall capabilities;
- local identity / lexical search;
- `SearchMethodSpec`, method/provider registries and explicit `MethodBinding`;
- typed Search Graph and deterministic plan validation;
- provider-neutral execution runtime;
- trusted policy / usage-envelope boundary;
- candidate-evidence, anchoring, provenance and append-only evidence history;
- Search Receipt persistence;
- Brave Web Search provider;
- Crossref scholarly metadata provider;
- EPO OPS Patent Intelligence provider and patent-domain methods;
- AI Daily / discovery / source-lineage research paths.

## Evidence boundary

Provider results are observations, not truth.

```text
ProviderObservation
    ≠ VerifiedEvidence

Search snippet
    ≠ Claim support

LLM recall
    ≠ External evidence
```

For high-risk research, source identity, version, anchor, temporal fit, semantic support, independence, and usage rights can be verified separately.

## MCP

MCP is an optional protocol face over capabilities.

```text
MCP = capability exchange protocol
MCP ≠ search intelligence
```

The canonical runtime should remain usable through Python, CLI, MCP, HTTP, or future agent interfaces without moving search semantics into the protocol layer.

## Naming / repository migration

Recommended future public repository name:

```text
omphalos
```

Alternative names:

```text
omphalos-runtime
omphalos-search
omphalos-ausi
```

The repository can be renamed independently of the Python import package. GitHub redirects old repository URLs after a rename, but package/import migration should be handled separately and deliberately.

## Status

Omphalos is under active research and incremental refactoring. The architecture is intentionally evolving through typed contracts, tests, provider adapters, domain packs, and evidence-aware research loops rather than a big-bang rewrite.

The crawler is still useful. It is simply no longer the identity of the project.

---

**One-line description**

> **Omphalos / AUSI Runtime — an AI-native search-method runtime that lets AI select, compose, execute, verify, and learn search strategies across replaceable models, search engines, APIs, databases, crawlers, and local corpora.**
