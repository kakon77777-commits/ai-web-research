# Omphalos / AUSI Runtime v1.0 — Final Release Gate Checkpoint

**Date:** 2026-09-07  
**RC merge base:** `c291567bcc4ec59bacdc90036819e0db264a2f23`

## Release identity

```text
package candidate for final publication = 1.0.0
public API                              = 1.0
historical RC                           = 1.0.0rc1
```

The final gate is a release-engineering milestone, not a search-feature milestone. Changes after the RC merge are limited to version promotion, final manifests/gates, release documentation, tests, and CI orchestration. The workflow rejects changes under `src/ai_web_research/` or `src/crawler/` relative to the merged RC base.

## RED baseline

The first final-gate clean checkout intentionally ran before promotion and produced:

```text
519 passed / 2 failed
```

Both failures were expected final-contract failures: current package still reported `1.0.0rc1`, and the final `1.0.0` API/manifest artifacts did not yet exist. No unrelated Runtime regression was present.

## G1–G9 and reference workflows

The final manifest and `omphalos.final_release` map each canonical G1–G9 gate to existing behavior/E2E tests and separately map General Web, Current X/Web, Academic/NPL, and Patent Prior-Art reference paths. GitHub Actions reruns those mappings explicitly in addition to the full repository suite.

## Artifact policy

The repository stores content-addressed API/benchmark/final-manifest inputs, but it intentionally does not store the SHA-256 of an sdist inside a document that is itself packaged into that sdist. Exact final source HEAD, package hashes, Actions artifact identity, PR state, and FINAL ZIP SHA-256 belong to external CI/PR/offline handoff evidence.

## Publication boundary

Passing this technical gate makes the final release PR eligible for explicit merge/tag authorization. It does not itself merge the release PR or create a tag.
