# ADR-025: Reviewed Workspace Intake Identity

## Status

Accepted source design under Epic #890. Runtime activation is not granted.

## Context

Workspace Intake needs OOS to prepare a reviewed canonical change without
borrowing personal credentials or repository-administration authority. The
authority repository is user-owned, unlike the organization-bound repository
creation workflow. GitHub content-write permission is not branch-specific and
also permits the merge API absent additional provider controls.

## Decision

Define a separate exact-repository GitHub App identity with Metadata read,
Contents write, Pull requests write and Checks read. Keep the definition
selected and inactive. Platform retains private-key custody and supplies only
short-lived token files to the admitted OOS profile after Security review.

Provider-enforced main-update and merge denial, with no App bypass, is an
activation prerequisite. OOS separately enforces the intake branch namespace,
owner-command file boundary, source binding, reviewed merge and readback.
Neither control is claimed to replace the other. The operator surface is
[Workspace Intake Git Identity](../../components/operator-orchestration-service/workspace-intake-identity.md).

## Consequences

Canonical ownership and human merge authority remain intact. Definition tests
can run without credentials. Activation requires real evidence and may be
blocked if the provider account cannot enforce the required boundary. #1066
reviews exact source; #1082 owns commissioning and rollback; #1069 owns composed
proof. The current [change record](../../records/change-records/2026-09-05-workspace-intake-identity-definition.md)
covers definition only; activation must leave its own operating evidence.

## Alternatives Considered

- Personal tokens or ambient `gh`: rejected because custody and authority are
  bound to an operator session rather than the admitted service identity.
- Existing repository lifecycle/provisioning App: rejected because its
  administrative authority is unnecessary and its organization scope differs.
- Application-only merge prohibition: insufficient because Contents write
  still grants provider capabilities beyond the application's normal actions.
