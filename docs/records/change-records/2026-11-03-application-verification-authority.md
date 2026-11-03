---
security_evidence:
  review_areas: [identity, secrets, delivery]
  reviewed_artifacts:
    - scripts/agent_source_bootstrap.py
    - scripts/test_agent_source_intent.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Active-owner application verification configuration

## Summary

Extend the existing finite owner-control source purpose to explicit
`configure-verification` requests from current active source-only Inventory.
This is operator-approved maintenance, not a new ART initiative or credential
class. Landing Unit Decision: `feature_single_landing_unit`; Landing Unit
`maintenance-application-verification-authority`.

## Classification

Operator-approved cross-repo repair with a separate Platform issuer review,
validation and rollback boundary. It extends an existing capability.

## Ownership

Platform owns source identity enforcement. Workspace Governance owns admission
policy; OOS owns workflow and receipts; Console is the operator adapter.
Security retains review authority. No role is transferred to an AI model.

## Root Cause

Existing bootstrap authority correctly excludes active owners. Reusing Proposed
Intake for later configuration would contradict active Inventory. The existing
issuer now distinguishes the explicit operation and independently reads the
exact active Inventory entry and provider binding. Ordinary source and
pre-Inventory bootstrap keep their existing authority.

## Source Changes

Only the verification profile, its schema, bootstrap profile digest and exact
known validator migration may change. No source, guidance, CI, workflow-write
permission, model invocation, admission or runtime authority is granted.
Inventory version/digest, lineage, source-only posture, unique provider and
current actor/source-intent checks remain required. Suspended, retired, stale,
Security-bound and other-path requests fail closed. Source authorization does
not imply passed application tests. Correct release guidance to its actual
implemented readiness validator; applicable production checks remain.

## Security and rollback

Review: [verification maturity delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-03-repository-verification-maturity.md).
The main agent retains Security closure and delegated accountable review.
Revert the coordinated issuer/OOS/Console extension; preserve original source
requests, credentials' revocation history, receipts and accepted profiles.

## Artifact And Deployment Evidence

Source validation precedes publication. Exact composed Security acceptance and
normal complete-runtime activation are required before live use. No new provider
App installation, permission grant or shared-secret boundary is introduced.

## Live Verification

The issuer tests verify active Inventory binding, unchanged four-permission
projection, original-request replay and rejection of stale/suspended/foreign
subjects. Console operating checks remain separate from source tests.

## Follow-Up

Owner: platform-engineering. Complete reviewed source landing, composed runtime
readback and exact Landing Unit credential/worktree cleanup.
