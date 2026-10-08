# ADR-028: Dedicated Proposal Target Identity

## Status

Accepted for the single-operator, loopback `dev-integration` boundary approved
by Security work item `#1235` and commissioned by Platform work item `#1236`.

## Context

Proposal Target application and Prototype Landing, Maturity, and Closure all
write reviewed changes to `workspace-prototype-studio`, but they have different
branch, path, lifecycle, audit, and rollback boundaries. Agent Gary is the
workspace source implementor and is not an application-runtime identity.
Reusing any of those principals would make unrelated workflow authority
indistinguishable and would prevent independent revocation.

## Decision

Use a separate selected-repository GitHub App with Metadata read, Contents
write, Pull requests write, and Checks read. Install it only on
`mfshaf7/workspace-prototype-studio`. Limit OOS use to deterministic
`proposal-target/<digest>` branches and `records/prototype-captures/**`.

Platform owns private-key custody and issues one short-lived exact-repository
token to the OOS Proposal Target runtime. OOS may create a branch and pull
request but cannot approve, merge, update `main`, bypass repository rules, or
write another Prototype workflow's paths. Human exact-head approval and merge
remain separate. Console receives no provider credential and the browser
receives no owner credential.

Source activation, provider identity delivery, loopback composition, operating
proof, rollback, and clean redelivery are one existing `#1236` Landing Unit.
They are not additional ART stories.

The controlling review is the
[Proposal Target Application Trust-Boundary Security Delta](https://github.com/mfshaf7/security-architecture/blob/e6cb227f6cadceed6a4c741ecabf243de0b6bf51/docs/reviews/components/2026-10-08-proposal-target-application-trust-boundary.md).

## Consequences

- Proposal Target can be suspended and revoked without changing Landing,
  Maturity, Closure, or Agent Gary.
- One dedicated GitHub App and Vault path must be commissioned.
- A prepared branch or merged review is not completion; OOS must verify target
  bytes and acknowledge the canonical Proposal.
- Stage, production, shared access, AI-driven application, and broader target
  paths remain excluded.

The operator surface is
[Proposal Target Identity](../../components/operator-orchestration-service/proposal-target-identity.md).
