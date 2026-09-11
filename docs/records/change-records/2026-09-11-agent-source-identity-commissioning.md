# Agent Source Identity Commissioning

## Summary

- Date: 2026-09-11
- Short title: Platform custody for the Agent source identity
- Environment: Local `dev-integration`; normal OOS consumption remains inactive
- Severity: Planned capability, not an incident

## Classification

ART #1136 under #920/#892. This source Landing Unit implements the Platform
credential boundary approved by Security #1135. It does not activate OOS source
operations; #1137 owns that separate consumer change.

## Ownership

Platform owns App private-key custody, exact-repository token issuance,
ephemeral projection, rotation, suspension, revocation, and rollback. OOS owns
the consuming source executor. Workspace Governance owns the Agent authority
contract. Security Architecture owns acceptance. `mfshaf7` remains human
reviewer and merger; Agent Gary remains source author and branch pusher.

## Root Cause

The authority contract and GitHub App existed, but the bootstrap key remained
temporary operator-local material and no Platform-owned one-repository runtime
projection existed. Activating OOS against ambient `gh` or human credentials
would collapse attribution, custody, and review boundaries.

## Source Changes

Added the exact Agent source identity definition and schema, Platform operator
command, provider and runtime tests, component guidance, and validation wiring.
The controller commissions every selected repository through a separate proof
token, stores the private key in Vault, atomically projects one ephemeral
Landing Unit credential, and supports fail-closed rotation, suspension, and
revocation without secret-bearing evidence.

## Artifact And Deployment Evidence

The finalized Review Packet will bind the exact Platform source head, local
CI-equivalent validation, provider commissioning receipt, and Security #1135
decision. No stage, production, Argo, image, or product release is part of this
change.

## Host Or Runtime Recovery

Suspend issuance, revoke exact projected credentials, and remove the ephemeral
runtime projection. Preserve source, provider history, human decisions, and
secret-free receipts. Recommission before resuming issuance; never reconstruct
a token from durable OOS state.

## Live Verification

Sandbox tests prove exact provider identity, immutable repository ids,
one-repository token scope, expiry checks, rotation rollback, suspension,
revocation, restart-safe re-read shape, bootstrap retirement, and value-free
receipts. The commissioning evidence is added to the Review Packet rather than
embedding secrets in this record.

## Follow-Up

ART #1137 binds this projection to the finite-action OOS source executor and
proves repository, branch, base, pushed-head, human-review, merged-head,
restart, and denial behavior before normal activation.
