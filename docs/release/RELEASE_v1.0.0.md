# Omphalos / AUSI Runtime 1.0.0

`1.0.0` is the first final package version for the frozen Omphalos v1 public API. It promotes the verified v0.9 RC without adding a new Search Method, Provider, Planner behavior, routing behavior, policy authorization path, evidence semantic, stopping semantic, learning behavior, evaluation algorithm, or crawler feature.

## Final identity

```text
Distribution:       ai-web-research
Package:            1.0.0
Public facade:      omphalos
Public API:         1.0
Historical RC:      1.0.0rc1
```

The historical RC artifacts are retained byte-for-byte. Final public contract descriptors must be identical to the RC descriptors.

## Canonical final gates

The Final Release Gate replays G1 Method, G2 Provider topology, G3 Replaceability, G4 Planner, G5 Policy, G6 Evidence, G7 Gap/Stop, G8 Receipt, and G9 Evaluation behavior tests on the exact release head.

It separately replays the four v1 reference paths: General Web, Current X/Web, Academic/NPL, and Patent Prior-Art. These are deterministic credential-free E2E/reference-path tests; they are not claims of live-provider availability or superiority.

## Benchmark boundary

The bundled v0.8 reference benchmark remains synthetic. Its report and manifest must exactly regenerate, and every benchmark manifest must replay. This is reproducibility evidence, not proof that Omphalos universally outperforms any live Provider.

## Security boundary

Credentials and hidden/private reasoning are not release artifacts. `UNKNOWN != ALLOW`, `Retrieved != Verified`, `Citation != Support`, `SearchReceipt != ChainOfThought`, and `Learning != SelfAuthorization` remain permanent release invariants.

## Packaging boundary

The final workflow builds wheel and sdist twice under a fixed `SOURCE_DATE_EPOCH`, requires identical SHA-256 values between the two builds, then installs the wheel into a fresh environment and runs imports plus offline CLI diagnostics from outside the source tree.

Exact final source HEAD, wheel/sdist hashes, GitHub Actions artifact hash, and offline FINAL ZIP hash are recorded outside the source package to avoid hash self-reference.

## Publication boundary

A release-branch package carrying version `1.0.0` is not considered published merely because it exists. Merge/tag/publication remain explicit release actions after the exact final PR head passes the Final Release Gate.
