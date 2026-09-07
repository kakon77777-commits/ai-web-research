# Omphalos / AUSI Runtime v0.9 — API Freeze / Hardening / RC Checkpoint

**Date:** 2026-09-07  
**Base master:** `ee490addeaac29efa7831df728950c0cad68f07e`

## RC identity

```text
package candidate = 1.0.0rc1
public API        = 1.0
release gate      = 0.9.0
final v1.0        = NOT YET
```

v0.9 freezes and hardens the existing Runtime. `ai_web_research` remains the implementation package; `omphalos` is the stable v1-facing facade. No new Provider, Search Method, Planner, Routing, Policy, Evidence, Stopping, Experience, Evaluation, or crawler behavior is introduced by this milestone.

## Frozen/hardened surfaces

- deterministic public API manifest: `release/omphalos-v1.0.0rc1-public-api.json`;
- 30 explicitly frozen public contracts exposed through the `omphalos` facade;
- stable `OmphalosErrorCode` / `ErrorDescriptor` / `OmphalosError` taxonomy;
- package metadata and `omphalos` console entry while preserving the `ai-web-research` distribution name and existing implementation packages;
- offline `version`, `api --json`, and `doctor --json` commands;
- API/migration, security/credential, reference-workflow, Quickstart, and RC documents;
- machine RC release gate and full-checkout GitHub Actions workflow;
- deterministic `release/omphalos-v1.0.0rc1-manifest.json` with `rc_not_final_v1=true`.

## First clean full-repository baseline

The first full checkout GitHub Actions gate ran against construction head `0de21b8dd131da8e9104a095669e27de898ae028`.

```text
dependency install / pip check: PASS
full repository pytest:          515 passed / 3 failed
```

All three failures were one deterministic release-artifact drift, not Runtime behavior:

```text
v0.8 reference fixture actual SHA-256:
80126f5955f738dd4f20c8d7e8e6b344df6e16e401bc921b1c4f9cc610515d19

inherited v0.8 reference manifest incorrectly recorded:
808b3d1371f21984a3e99ddebc2a8f9b5383b9698ccb8b0889b177e0606c494e
```

That caused:

1. v0.8 suite artifact exact-regeneration failure;
2. v0.9 RC manifest exact-regeneration failure;
3. v0.9 release gate failure.

The minimal fix regenerated only `benchmarks/artifacts/omphalos-v0.8-reference-manifest.json` from the canonical fixture. No benchmark runner, fixture semantics, or Runtime behavior was changed.

## Clean full-repository RC gate

GitHub Actions run:

```text
run id  = 34091459175
job id  = 101645602182
head    = 6dd7e28ff1f7cafd19255058e463808781ee925b
result  = SUCCESS
Python  = 3.11.16
```

Fresh full-repository verification:

```text
pip install -e '.[dev]' / pip check: PASS
pytest -q:                           518 passed in 5.12s
compileall src + tests:              PASS
Omphalos release gate:              PASS
reproducible build A/B hash diff:    PASS
fresh wheel install --no-deps:       PASS
outside-source import smoke:         PASS
omphalos version:                    PASS
omphalos doctor --json:              PASS
```

Release gate output:

```text
PASS package_version: 1.0.0rc1
PASS wheel_packages: implementation + facade
PASS console_script: omphalos.cli:main
PASS public_api_manifest: 30 contracts
PASS public_api_forbidden_fields: none
PASS release_docs: 5 files
PASS benchmark_artifacts: 3 files
PASS rc_manifest: content-addressed and reproducible
PASS literal_secret_scan: no literal credential assignments/raw tokens
PASS rc_workflow: .github/workflows/omphalos-rc.yml
```

## Reproducible package hashes

Build A and Build B produced identical SHA-256 values under fixed `SOURCE_DATE_EPOCH=1788449640`:

```text
ai_web_research-1.0.0rc1-py3-none-any.whl
3429179ab3f146b029373e3d018296831549f953e04878cfb2cbde96be3f0547

ai_web_research-1.0.0rc1.tar.gz
2e40ce93031f50ffea8c8cadddb7861f22209f8e376809cf0a801f0e45fa4f43
```

Clean wheel smoke from outside the source tree reported:

```text
package version      = 1.0.0rc1
public API version   = 1.0
public contracts     = 30
error codes          = 18
network required     = false
credential required  = false
status               = ok
```

GitHub Actions RC artifact:

```text
artifact name   = omphalos-v1.0.0rc1-package
artifact id     = 10006984117
artifact SHA256 = 325649ca7a91245b7993690dbcd42b5b800d251381dd9869a5890bbac17b91e4
```

This CI artifact is an RC package artifact, not the final v1.0 distribution.

## Security / reasoning boundary

The v0.9 release gate scans production `src/` and `scripts/` for literal credential assignments and raw token shapes, and rejects forbidden serialized public-API fields including:

```text
chain_of_thought
private_reasoning
hidden_reasoning
credential_value
raw_credential
```

Security documentation additionally preserves:

```text
Planning != Authorization
UNKNOWN != ALLOW
SearchReceipt != ChainOfThought
Learning != SelfAuthorization
ProviderGrounding != VerifiedEvidence
Citation != Support
```

## Reference workflows

The RC documents four reference paths:

```text
General Web Research
X / Current Discourse Research
Academic / NPL Research
Patent Prior-Art Research
```

All retain explicit Search Method / Provider / acquisition / evidence / gap / stop boundaries and do not treat Provider grounding, social posts, metadata discovery, or patent family heuristics as VerifiedEvidence.

## Final v1 boundary

`1.0.0rc1` is not final v1.0. The next milestone is the v1.0 Final Release Gate: final-HEAD verification, clean-package verification, reference workflow verification, benchmark replay, security/secret scan, reproducible final package, FINAL ZIP, SHA-256, release tag, and final release artifacts.

Before opening the v0.9 PR, the construction history must be replayed as one milestone commit on the latest master, and the exact resulting PR head must pass this same clean full-repository RC workflow again.