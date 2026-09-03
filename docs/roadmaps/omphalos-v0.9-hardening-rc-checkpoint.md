# Omphalos / AUSI Runtime v0.9 — API Freeze / Hardening / RC Checkpoint

**Date:** 2026-09-03  
**Base master:** `ee490addeaac29efa7831df728950c0cad68f07e`

## RC identity

```text
package candidate = 1.0.0rc1
public API        = 1.0
release gate      = 0.9.0
final v1.0        = NOT YET
```

v0.9 freezes and hardens the existing Runtime. `ai_web_research` remains the implementation package; `omphalos` is the stable v1-facing facade.

## Frozen/hardened surfaces

- deterministic public API manifest: `release/omphalos-v1.0.0rc1-public-api.json`;
- stable `OmphalosErrorCode` / `ErrorDescriptor` / `OmphalosError` taxonomy;
- package metadata and `omphalos` console entry;
- offline `version`, `api --json`, and `doctor --json` commands;
- API/migration, security/credential, reference-workflow, Quickstart, and RC documents;
- machine RC release gate and full-checkout GitHub Actions workflow;
- deterministic `release/omphalos-v1.0.0rc1-manifest.json` with `rc_not_final_v1=true`.

## Local verification before GitHub final tree

```text
v0.9 concise targeted RC tests: PASS
release gate: 10/10 PASS
compileall: PASS
public API exact regeneration: PASS
RC manifest exact regeneration: PASS
```

Earlier compatibility materialization also passed the v0.7 + v0.8 + v0.9 local compatibility gate. Local materialization results are not relabeled as a full current-repository run.

## Full-repository gate

The exact PR head must pass GitHub Actions on a full checkout:

```text
pytest -q
python -m compileall -q src tests
python scripts/omphalos_release_gate.py
python -m build
clean wheel install --no-deps
omphalos version
omphalos doctor --json
```

Until that workflow passes, the RC is not called full-repo ready.

## Final v1 boundary

`1.0.0rc1` is not final v1.0. The next milestone is the v1.0 Final Release Gate: final-HEAD verification, clean-package verification, reference workflow verification, benchmark replay, security/secret scan, reproducible final package, FINAL ZIP, SHA-256, release tag, and final release artifacts.