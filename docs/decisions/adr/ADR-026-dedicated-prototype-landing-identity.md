# ADR-026: Dedicated Prototype Landing Identity

## Status

Accepted for local `dev-integration` identity projection. Workflow activation
remains pending composed conformance.

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

Identity projection and workflow activation are separate. #1090 may project
the credential and runtime dependencies while forcing the workflow disabled.
Normal availability requires the later Console and composed conformance gates.

## Consequences

- compromise is limited to one repository and one review-branch workflow;
- runtime teardown does not erase source, review, or coordination evidence;
- one additional App and Vault path must be commissioned and rotated; and
- OOS and WGCF activation cannot be claimed from Platform evidence alone.

The operator procedure is
[Prototype Landing Identity](../../components/operator-orchestration-service/prototype-landing-identity.md).
