---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime, ai]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console Source Authoring — staged Platform source

## Summary

- Date: 2026-10-18.
- Environment: source preparation for local dev-integration, not a deployment.
- Severity: missing Console-only capability, not a reproduced provider failure.
- Landing Unit: maintenance-1275-prototype-authoring-platform;
  child_isolated_landing_unit for the actual Platform repository/rollback boundary.
- Work state: existing Epic1275/qualification1298 and operating-truth candidate;
  operator-approved maintenance path, no new repair child.

## Classification

Extend the existing source issuer and authenticated Platform provider. Operator
approved the bounded issue/renew/revoke extension on October18. No App permission,
selected repository, model, public hosting or runtime activation is granted.

## Ownership

Platform owns custody, issuance, private projections and owner receipts. OOS
owns canonical subject/source-intent authorization and bounded execution;
Console is its typed adapter. Workspace Governance owns admission; Security
owns final exact-source acceptance. Human reviewer/merger remains mfshaf7;
source implementation/publication remains Agent Gary. Decision:
[ADR-029](../../decisions/adr/ADR-029-source-intent-credential-effects.md).

## Root Cause

Existing before-session credential gating is correct, but a fresh normal
source path relies on engineering delivery. Earlier reuse did not establish
that Console could complete this step through an owned API. This source unit
fills the producer seam; it does not classify all existing publication as broken.

## Source Changes

Reuse the exact issuer transaction from engineering deliver in the finite
provider. Add closed real Delivery/Prototype bindings, pre-session intent,
single session binding, serialized issue/renew/revoke, private durable intent
metadata and revocation tombstones. Preserve strict repository/provider
identity, original credential format, separate bootstrap authority and human
review. Atomic state writes also fsync their parent directory. Unknown issuance
is not reminted or falsely called revoked; only safe typed failure metadata
crosses the provider. No source branch/worktree is created by these actions.

## Artifact And Deployment Evidence

Base: ac854a4e08a6d075bd1842127513c55de59f3997. Candidate validation and exact
review head will be recorded with this Landing Unit. No image, Argo revision,
stage/prod change or new runtime acceptance exists. Existing exact Platform
tree/Security consumers require coordinated reacceptance before commissioning.

## Host Or Runtime Recovery

None performed. Keep accepted primary/runtime unchanged during source
preparation. Rollback disables these finite actions through the prior accepted
composition, revokes exact owned projections and preserves non-secret intent,
command and source history. Do not erase tombstones to resume a cancelled intent.
An explicitly approved successor references its exact revoked predecessor while
preserving the Landing Unit; branch rotation does not create another ART item.

## Live Verification

Sandbox proof exercises the real issuer against loopback provider HTTP, private
projection, actual authenticated Platform API, replay/cold reconstruction,
concurrency, expiry/renewal, revocation and scope denials. This is engineering
evidence, not Console-operated credentials, to-do generation or Epic acceptance.
No live credential automation has been activated.

## Follow-Up

Finish dependent OOS/Console authorization and source action guards; prepare
remaining owner contracts/consumers; acquire final exact composed Security delta
acceptance and generated Security record index after owner source lands; then
commission coherently and obtain the real Console operating witness. Existing
Studio/WG merge hold remains in effect. Source publishing/credential revocation,
open-PR custody and final branch retirement follow the existing normal path.
