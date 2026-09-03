# Omphalos v1 Security and Credentials

## Credential boundary

API keys, OAuth tokens, passwords, private keys, and equivalent secrets are runtime credentials, not research artifacts.

Allowed locations include:

- process environment;
- operating-system or deployment secret manager;
- runtime credential profile;
- transient `ExecutionContext` services supplied by the host.

Credentials must not be persisted into:

- `ProviderState` metadata;
- Search Receipt or Search Action Receipt;
- Evidence or Provenance records;
- Planner Prior / Experience datasets;
- benchmark artifacts;
- source-controlled fixtures;
- release manifests;
- ordinary logs.

`ProviderState` may record only non-secret state such as `credential_available=True/False`.

## Policy boundary

```text
UNKNOWN != ALLOW
Planning != Authorization
Learning != SelfAuthorization
```

The Planner may propose actions. Provider routing may select an eligible channel. Historical Experience may influence preference. None of these grants permission.

Only the Policy authorization layer can produce an executable authorization decision.

## Receipt and reasoning boundary

```text
SearchReceipt != ChainOfThought
```

Receipts contain externally observable facts required for audit and replay. Hidden reasoning, private model reasoning, provider thought traces, and credentials are not receipt fields.

## Provider-grounded output

A grounded model answer or search citation is not automatically verified evidence:

```text
ProviderGrounding != VerifiedEvidence
Citation != Support
```

Source references must pass the normal acquisition/evidence/provenance path.

## Error metadata

The public RC error facade rejects metadata keys matching credential-like names such as API keys, access tokens, refresh tokens, client secrets, private keys, passwords, or credential values.

## Incident handling

If a credential is exposed:

1. revoke/rotate the credential outside Omphalos;
2. remove it from all runtime logs and artifacts;
3. do not preserve the secret merely for audit;
4. preserve only non-secret incident references/hashes if needed;
5. rerun release secret scans before distribution.
