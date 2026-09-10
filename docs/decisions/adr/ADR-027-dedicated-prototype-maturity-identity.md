# ADR-027: Dedicated Prototype Maturity Identity

## Status

Accepted. Normal availability remains a sequenced set of independent Security,
WGCF, OOS, Platform, and Console controls.

## Context

Prototype Maturity prepares candidate and baseline-promotion changes in
`workspace-prototype-studio`. The existing Prototype Landing identity targets
the same repository but has different branch, path, workflow, audit, revocation,
and rollback semantics. Reusing it would couple independently governed actions
and make one workflow impossible to revoke without affecting the other.

## Decision

Define a separate selected-repository GitHub App identity with Metadata read,
Contents write, Pull requests write, and Checks read. Limit OOS use to
`prototype-maturity/<digest>` review branches and the exact Prototype registry,
maturity-record, and design-baseline paths. Platform owns private-key custody
and short-lived token delivery. OOS cannot merge, update `main`, mutate
Landing or Closure paths, or use ambient credentials.

Definition, Security approval, WGCF activation, OOS activation, Platform
commissioning, and Console operating proof remain independent controls. This
decision defines authority; each activation remains separately reviewable and
reversible.

Platform commissioning composes the two runtime gates in dependency order:
WGCF readiness is enabled before OOS admits Maturity work. Suspension and
revocation reverse that order by disabling or removing the OOS projection
before the WGCF gate. Prototype Landing configuration is outside this rollback
boundary.

The controlling Security inputs are the accepted-with-findings
[Prototype Maturity Trust-Boundary Review](https://github.com/mfshaf7/security-architecture/blob/61c96e53cf87491e8d42ba076fa241844b5132e5/docs/reviews/components/2026-09-09-prototype-maturity-trust-boundary.md),
the [Identity and Access](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/identity-and-access.md)
and [Secrets and Recovery](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/standards/secrets-and-recovery.md)
standards, and the [GitOps and Machine Trust](https://github.com/mfshaf7/security-architecture/blob/2814c54542e020913af37c5805f953ec18864e05/docs/architecture/domains/gitops-and-machine-trust.md)
domain. The final normal-availability review is
[`#1125`](https://github.com/mfshaf7/security-architecture/blob/087118a5f79034684f0ca895a85cb735d1298627/docs/reviews/components/2026-09-10-prototype-maturity-normal-availability.md).

## Consequences

- Landing and Maturity can be suspended, revoked, and rolled back separately.
- One additional GitHub App and Vault path are commissioned independently.
- Shared repository scope does not imply shared workflow authority.
- Normal Console availability remains blocked until ART #1132 completes
  against the exact commissioned runtime.

The operator surface is
[Prototype Maturity Identity](../../components/operator-orchestration-service/prototype-maturity-identity.md).
