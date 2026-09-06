# Workspace Intake Identity Activation

## Summary

- Date: 2026-09-06
- Short title: Activate the bounded Workspace Intake GitHub App identity
- Environment: `dev-integration`
- Severity: Planned capability activation, not an incident

## Classification

ART #1082 under #1061/#890; source Landing Unit
`delivery-890-git-identity-activation`. This record covers the first bounded
runtime activation and rollback proof. Composed intake conformance remains
owned by #1069.

## Ownership

Platform owns private-key custody, short-lived token issuance, delivery,
rotation, and revocation. OOS consumes the token only for the accepted
Workspace Intake workflow. Workspace Governance owns repository policy and
reviewed source truth. Security review #1066 approved the exact boundary with
findings that #1069 must close in composed proof.

Related decision:
[ADR-025](../../decisions/adr/ADR-025-reviewed-workspace-intake-identity.md).

## Root Cause

The reviewed intake workflow had a selected identity contract but no active,
least-privilege credential path. Existing personal or administrative
credentials would exceed the required repository and operation boundary.

## Source Changes

Added the operator command that validates GitHub provider readback before it
commissions, delivers, rotates, or revokes the Workspace Intake identity. The
implementation binds App, installation, owner, repository, permission, event,
caller, source-revision, expiry, and rollback evidence. Kubernetes delivery
uses server-side apply and teardown removes the exact mount, volume, Secret,
and environment projection.

The implementation landed through platform-engineering PR #230. PR #231
corrected the Kubernetes merge-key teardown and removed client-side Secret
payload persistence from the last-applied annotation before final activation.

## Artifact And Deployment Evidence

- GitHub App id: `4845505`
- installation id: `159392456`
- exact repository: `mfshaf7/workspace-governance` (`1212447211`)
- active repository ruleset: `22344505`
- private-key custody: the contracted Platform Vault path for Workspace Intake
- token projection: read-only OOS Secret mount in `dev-integration`
- implementation source: platform-engineering `2af71b8c73e16f1484cfa5432deb6e4c930b3244`

No private key or installation token is stored in source, this record, or the
runtime receipts.

## Live Verification

Provider readback confirmed the exact personal-account owner, selected-repo
installation, required permissions, empty event subscription, and absence of
unrelated repository access. A short-lived token was delivered to the active
OOS runtime and the service returned healthy. Rotation then proved provider
revocation and complete runtime teardown before a fresh token was issued and
delivered. The corrected Secret carried no client-side last-applied payload.

## Follow-Up Actions

#1069 must prove the composed Console-to-OOS-to-WGCF-to-Workspace-Governance
path, including candidate-source authenticity, reviewed pull-request creation,
human merge authority, protected-main denial, and canonical readback. Revoke
the runtime token and remove its OOS projection when the bounded proof no
longer needs it.
