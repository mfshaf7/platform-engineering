# Prototype Maturity Identity

## Role And State

Platform defines one dedicated GitHub App identity for OOS Prototype Maturity.
Its only repository is `mfshaf7/workspace-prototype-studio`, immutable id
`1231020532`, owned by user id `244414185`. It is separate from Prototype
Landing even though both target the same repository.

The definition is **selected, not active**. No App or installation id has been
assigned, no credential has been issued, and the workflow gate remains off.
The authoritative definition is
[prototype-maturity-identity.yaml](../../../security/prototype-maturity-identity.yaml).

## Primary Operator Path

```bash
make prototype-maturity-identity ACTION=validate
python3 scripts/test_prototype_maturity_identity.py
```

Validation is read-only and reports the exact definition digest. There is no
commission, delivery, suspension, or revocation command in source-definition
work #1128. Platform commissioning #1131 adds those operations only after
Security #1125, WGCF #1129, and OOS #1130 have landed.

## Security Authority

The inactive definition is bound to Security Architecture review
[`#1098`](https://github.com/mfshaf7/security-architecture/blob/61c96e53cf87491e8d42ba076fa241844b5132e5/docs/reviews/components/2026-09-09-prototype-maturity-trust-boundary.md),
which accepted the implementation foundation with findings but did not approve
normal availability. Its machine-identity, custody, and recovery controls apply
the revision-pinned [Identity and Access](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/identity-and-access.md),
[Secrets and Recovery](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/secrets-and-recovery.md),
and [GitOps and Machine Trust](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/architecture/domains/gitops-and-machine-trust.md)
requirements. Final Security decision #1125 must review this exact definition
and the composed conformance evidence before activation.

## Least Privilege

The App uses Metadata read, Contents write, Pull requests write, and Checks
read for exactly `workspace-prototype-studio`. OOS may prepare only
`prototype-maturity/<digest>` review branches and may change only:

- `prototypes.yaml`
- `records/prototype-maturity/**`
- `records/design-baselines/**`

The identity cannot merge, update `main`, administer or delete repositories,
mutate Landing or Closure paths, mutate referenced source, or access another
repository. GitHub permissions do not enforce file paths and the merge API is
covered by Contents write, so activation must separately prove provider rules
that restrict `main` updates to approved humans, deny App bypass, require exact-
head review and trusted validation, dismiss stale approvals, and deny force
push and branch deletion.

## Custody And Evidence

The future private key belongs in the dedicated Platform Vault path declared by
the contract. OOS may receive only a rotating installation token through a
read-only Secret directory and a separate WGCF caller binding. Private keys,
tokens, caller secrets, and authorization headers must not enter source, logs,
receipts, ART evidence, or Console projections.

Commissioning must bind exact source revisions, provider ids, permissions,
runtime profile and session, Security approval, WGCF and OOS implementations,
restart survival, rotation, suspension, revocation, rollback, and value-free
receipts. Filesystem validation in this work proves only the inactive contract.

## Owner Sequence

1. #1128 defines and validates the inactive identity.
2. #1125 accepts or rejects the exact identity and conformance revisions.
3. #1129 and #1130 activate WGCF readiness and OOS orchestration independently.
4. #1131 commissions the runtime identity and proves recovery and revocation.
5. #1132 proves the normal Console path before Prototype closure begins.
