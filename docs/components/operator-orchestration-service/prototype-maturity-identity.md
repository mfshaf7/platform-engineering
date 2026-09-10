# Prototype Maturity Identity

## Role And State

Platform defines one dedicated GitHub App identity for OOS Prototype Maturity.
Its only repository is `mfshaf7/workspace-prototype-studio`, immutable id
`1231020532`, owned by user id `244414185`. It is separate from Prototype
Landing even though both target the same repository.

The definition authorizes a dedicated `dev-integration` projection after the
exact Security, WGCF, and OOS activation revisions are present. Platform may
commission, deliver, rotate, suspend, and revoke only this identity. The
authoritative definition is
[prototype-maturity-identity.yaml](../../../security/prototype-maturity-identity.yaml).

## Primary Operator Path

```bash
make prototype-maturity-identity ACTION=validate
make prototype-maturity-identity ACTION=commission ARGS="<identity arguments>"
make prototype-maturity-identity ACTION=deliver ARGS="<identity and runtime arguments>"
make prototype-maturity-identity ACTION=suspend ARGS="<identity and runtime arguments>"
make prototype-maturity-identity ACTION=revoke ARGS="<identity, runtime, and rollback arguments>"
```

`validate` is read-only. `commission` verifies the exact selected-repository
installation and revokes its proof token. `deliver` projects one rotating
installation token and one dedicated WGCF caller secret into the admitted OOS
profile, enables the dedicated WGCF readiness gate first, mounts Prototype
Studio read-only, retains a separate persistent state path, and restarts the
broker before revoking the prior token. `suspend` disables OOS admission before
disabling WGCF readiness without deleting state. `revoke` removes the OOS
projection before removing the WGCF gate and retains source, history, and
evidence. All three runtime actions require the exact admitted WGCF service URL;
they do not alter Prototype Landing or remove the shared OOS runtime-profile
configuration.

## Security Authority

The inactive definition is bound to Security Architecture review
[`#1098`](https://github.com/mfshaf7/security-architecture/blob/61c96e53cf87491e8d42ba076fa241844b5132e5/docs/reviews/components/2026-09-09-prototype-maturity-trust-boundary.md),
which accepted the implementation foundation with findings but did not approve
normal availability. Its machine-identity, custody, and recovery controls apply
the revision-pinned [Identity and Access](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/identity-and-access.md),
[Secrets and Recovery](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/secrets-and-recovery.md),
and [GitOps and Machine Trust](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/architecture/domains/gitops-and-machine-trust.md)
requirements. Final Security decision
[`#1125`](https://github.com/mfshaf7/security-architecture/blob/087118a5f79034684f0ca895a85cb735d1298627/docs/reviews/components/2026-09-10-prototype-maturity-normal-availability.md)
approved bounded activation with findings. The Platform operator fail-closes
unless the exact merged WGCF, OOS, and Security revisions are supplied.

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

The private key belongs in the dedicated Platform Vault path declared by
the contract. OOS may receive only a rotating installation token through a
read-only Secret directory and a separate WGCF caller binding. Private keys,
tokens, caller secrets, and authorization headers must not enter source, logs,
receipts, ART evidence, or Console projections.

Commissioning binds exact source revisions, provider ids, permissions,
runtime profile and session, Security approval, WGCF and OOS implementations,
restart survival, rotation, suspension, revocation, rollback, and value-free
receipts. The shared mechanism lives in `prototype_workflow_identity.py`; the
Landing and Maturity commands remain separate contract-specific entrypoints.

## Owner Sequence

1. #1128 defined and validated the inactive identity.
2. #1125 approved the exact identity and conformance revisions with findings.
3. #1129 and #1130 activated WGCF readiness and OOS orchestration independently.
4. #1131 commissions the runtime identity and proves recovery and revocation.
5. #1132 proves the normal Console path before Prototype closure begins.
