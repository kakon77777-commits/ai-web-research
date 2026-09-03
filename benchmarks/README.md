# Omphalos v0.8 Benchmark Suite

This directory contains the canonical **synthetic** reference benchmark suite for the Omphalos / AUSI Runtime v0.8 evaluation harness.

## Scope

The reference fixture validates benchmark mechanics for:

- Provider substitution
- Method diversity
- Adaptive / gap-directed planning
- Provenance independence
- Replay / reproducibility

## Critical limitation

**This synthetic reference suite does not demonstrate live-Web superiority.**

It also does not demonstrate empirical superiority over any live Provider, model, search engine, or production research workflow.

The fixture is deliberately deterministic so that the evaluation protocol, paired-case comparison, metric direction, provenance accounting, and reproducibility behavior can be tested without network availability, credentials, quota drift, or Provider changes.

Real evaluation should reuse the same harness with separately captured **live Provider / live Web** observations and clearly identify those datasets as empirical rather than synthetic.

## Fair-comparison rules

Every compared variant must cover the same case IDs. Unknown metric values remain unknown rather than becoming zero. Source mentions are distinct from independent source roots. Every report records baseline identity, metric direction, spec snapshot, dataset snapshot, and report identity.
