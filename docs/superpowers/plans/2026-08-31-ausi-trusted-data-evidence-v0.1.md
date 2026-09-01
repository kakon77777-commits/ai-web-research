# AUSI Trusted Data & Evidence v0.1 Implementation Plan

**Goal:** Connect executable AUSI ProviderObservations to a deterministic policy/evidence bridge implementing the first WP-03 slice without changing legacy `src/crawler/*` behavior.

**Architecture:** A SearchAction is evaluated against versioned SourcePolicyProfiles before execution. Executable policy decisions carry a UsageEnvelope seed. Successful ProviderObservations materialize AcquiredAssets; extraction observations materialize CandidateEvidence and deterministic EvidenceAnchors. Evidence state changes are append-only in a SQLite reference ledger and project explicit EvidenceGap states back toward planning. Policy, evidence quality, and usage rights remain separate.

**Tech:** Python >=3.11 stdlib, sqlite3, existing AUSI contracts, pytest.

## Global constraints

- No `src/crawler/*` modification.
- No new runtime dependency.
- `Robots != Authorization`.
- `UNKNOWN != ALLOW`.
- Only ALLOW / ALLOW_WITH_OBLIGATIONS may execute.
- Rights metadata travels with acquired/derived assets.
- `ProviderObservation != AcquiredAsset != VerifiedEvidence`.
- `quote_verified == anchor verification only`, never semantic support.
- LLM recall never becomes external verified evidence.
- Policy profiles are deterministic/manual in v0.1; no free-form LLM Terms interpretation.
- Evidence ledger is append-only by default.

## Task 1 — Policy models, registry, evaluator

Create `ai_web_research/policy/{models,registry,evaluator}.py` and tests.

RED/GREEN requirements:
- same-id/version conflicting policy profile is rejected;
- no applicable policy => UNKNOWN;
- explicit prohibition => DENY;
- permission only => ALLOW;
- permission + duty/constraint => ALLOW_WITH_OBLIGATIONS;
- robots disallow blocks CRAWL but robots allow alone never grants permission;
- stale high-risk policy => REVIEW;
- evaluator produces a UsageEnvelopeSeed and current policy refs.

## Task 2 — Trusted acquisition materialization

Create `ai_web_research/evidence/models.py` acquisition-side types and `materialize.py`.

RED/GREEN requirements:
- AuthorizedAction can carry an optional usage seed without breaking existing tests;
- ProviderObservation artifacts materialize AcquiredAssets with provenance and UsageEnvelope;
- one Observation can materialize multiple assets;
- source usage envelope IDs remain attached;
- failed observations do not materialize successful assets.

## Task 3 — CandidateEvidence and anchor bridge

Create `evidence/{anchors,verifier}.py` and tests.

RED/GREEN requirements:
- extraction `EVIDENCE_CANDIDATE` observation creates one CandidateEvidence per extracted field;
- `source_quote` maps to TEXT_SPAN EvidenceAnchor;
- legacy `quote_verified=True` maps to VerificationDimension.ANCHOR=PASS only;
- quote_verified false/missing => anchor FAIL / UNVERIFIED_ANCHOR gap candidate;
- semantic-support state remains UNKNOWN;
- `llm_recall` candidates never materialize as external EvidenceObjects.

## Task 4 — SQLite append-only ledger + GapProjection

Create `storage/trusted_sqlite.py`, `evidence/ledger.py`, `gaps/projection.py`, tests.

RED/GREEN requirements:
- persist policy profiles, usage envelopes, acquired assets, anchors, candidate evidence, ledger events, gap projections;
- ledger sequence is monotonic and old events are never overwritten;
- anchor failure projects UNVERIFIED_ANCHOR;
- missing source identity projects MISSING_IDENTITY;
- policy restricted asset projects POLICY_RESTRICTED_SOURCE;
- persisted records round-trip.

## Task 5 — Trusted runtime closure

Create `execution/trusted.py` and end-to-end tests using fake adapters.

Target loop:

`SearchAction -> PolicyEvaluator -> AuthorizedAction -> ExecutionRuntime -> ProviderObservation -> UsageEnvelope -> AcquiredAsset -> CandidateEvidence/Anchor -> Ledger -> GapProjection`

Acceptance:
- ALLOW path reaches materialized trusted/evidence state;
- UNKNOWN/DENY never executes adapter;
- extraction observation reaches candidate evidence + anchor verification + ledger;
- no semantic SUPPORT relation is fabricated;
- full AUSI suite and compileall pass;
- GitHub compare still shows no `src/crawler/*` modification.
