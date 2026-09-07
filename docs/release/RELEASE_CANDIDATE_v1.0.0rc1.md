# Omphalos / AUSI Runtime 1.0.0rc1 Release Candidate

`1.0.0rc1` is the v0.9 release candidate. It is **not the final v1.0 release**.

The RC freezes the proposed public facade and focuses on hardening rather than adding new search behavior.

## RC scope

- public `omphalos` facade;
- public API manifest/version `1.0`;
- stable error taxonomy;
- package metadata and offline CLI diagnostics;
- migration and deprecation policy;
- credential/security policy;
- four reference workflows;
- automated release gate;
- wheel/sdist build and clean wheel-install CI;
- deterministic RC manifest.

## Existing v1 candidate capabilities

The Runtime already contains the v0.2–v0.8 milestones: Provider state/routing, Search Method Corpus, autonomous planning, stopping/coverage/saturation, evidence/provenance closure, Search Experience learning, and evaluation/benchmarking.

## Evaluation claim boundary

The repository's bundled v0.8 reference benchmark is synthetic.

It is not live Provider empirical evidence and must not be presented as proof that Omphalos universally outperforms Brave, Grok, Gemini, Crossref, EPO, or any other live Provider.

## Legacy package name

The distribution remains named `ai-web-research` for this RC to avoid package/import churn. The stable v1-facing facade is `omphalos`.

## Final gate still required

Promotion from RC to final release requires the **v1.0 Final Release Gate**, including final-HEAD verification, clean package verification, reference workflow verification, benchmark replay, secret scan, reproducible final package, FINAL ZIP, SHA-256, and release tag.

No RC artifact should be relabeled as final v1.0 before that gate passes.
