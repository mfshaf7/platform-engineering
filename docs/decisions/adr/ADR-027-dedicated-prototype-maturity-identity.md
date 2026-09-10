# ADR-027: Dedicated Prototype Maturity Identity

## Status

Accepted as an inactive source definition. Security approval and runtime
activation remain separate downstream decisions.

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
and later short-lived token delivery. OOS cannot merge, update `main`, mutate
Landing or Closure paths, or use ambient credentials.

Definition, Security approval, WGCF activation, OOS activation, Platform
commissioning, and Console operating proof remain independent controls. This
decision defines authority but does not activate it.

## Consequences

- Landing and Maturity can be suspended, revoked, and rolled back separately.
- One additional GitHub App and Vault path must eventually be commissioned.
- Shared repository scope does not imply shared workflow authority.
- Normal availability remains blocked until ART #1125 and #1129 through #1132
  complete against the exact reviewed revisions.

The operator surface is
[Prototype Maturity Identity](../../components/operator-orchestration-service/prototype-maturity-identity.md).
