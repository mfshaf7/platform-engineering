# ADR-026: Dedicated Prototype Landing Identity

## Status

Accepted and active for local `dev-integration`. Composed Console conformance
remains a separate downstream proof.

## Context

Prototype Landing prepares reviewed source in `workspace-prototype-studio`.
Existing Workspace Intake and repository-provider identities either target a
different repository or carry broader administration authority. Reusing one
would blur repository, action, audit, and rollback boundaries.

## Decision

Use a dedicated, selected-repository GitHub App installation with Metadata
read, Contents write, Pull requests write, and Checks read. Platform owns its
private key, short-lived token delivery, rotation, revocation, runtime mounts,
and value-free receipts. OOS owns branch and path enforcement and cannot merge.
GitHub rules protect `main` from App updates or bypass.

Identity projection and workflow activation remain separate controls. Platform
#1114 may enable the OOS source-owned gate only with the exact Security #1111,
WGCF #1112, and OOS #1113 bindings. Console authority and composed conformance
remain outside that Platform activation.

## Consequences

- compromise is limited to one repository and one review-branch workflow;
- runtime teardown does not erase source, review, or coordination evidence;
- one additional App and Vault path must be commissioned and rotated; and
- OOS and WGCF activation cannot be claimed from Platform evidence alone.

The operator procedure is
[Prototype Landing Identity](../../components/operator-orchestration-service/prototype-landing-identity.md).
