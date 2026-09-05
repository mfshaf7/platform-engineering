---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# Workspace Intake Identity Definition

## Summary

- Date: 2026-09-05
- Short title: Selected, inactive Workspace Governance Git identity
- Environment: Source-only definition for dev-integration
- Severity: Planned capability, not an incident

## Classification

ART #1065 under #1061/#890; source Landing Unit
`delivery-890-git-identity-definition`. No runtime activation is included.

## Ownership

Platform owns credential custody and activation. OOS owns workflow and source
coordination; Workspace Governance owns policy and canonical YAML; WGCF owns
readiness; Security #1066 owns acceptance. #1082 owns activation.

Related decision: [ADR-025](../../decisions/adr/ADR-025-reviewed-workspace-intake-identity.md).

## Root Cause

The reviewed intake workflow needs a distinct source identity. Existing
repository-administration Apps are not least privilege for this operation.

## Source Changes

Added the exact-repository selected definition, strict schema, read-only
validator and filesystem conformance tests, with one primary operator surface.
The contract captures provider-enforced main and merge denial separately from
OOS branch/file restrictions. Validation rejects wider permissions, PATs,
ambient identity, premature activation, missing revocation and secret exposure.

## Artifact And Deployment Evidence

Source heads, owner tests and CI-equivalent commands bind the Review Packet.
No deployed image, live token or new App is claimed by this definition.

## Host Or Runtime Recovery

None. This work does not change host, cluster, Vault or provider configuration.

## Live Verification

Read-only GitHub repository identity confirmed the exact repository id and
personal-account owner. Definition tests prove configuration denial and restore,
not live authorization. Live provider and token proof is reserved for #1082
after #1066. Composed workflow proof remains #1069.

## Follow-Up

Revert this source unit independently while retaining all existing authority
and review evidence. #1082 implements and verifies credential delivery,
rotation, suspension and revocation through the approved contract. Runtime
must remain unavailable until its required evidence exists.
