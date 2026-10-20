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
approved the bounded issue/renew/revoke extension on October18. On October19
the operator separately approved and enabled Gary App Workflows write for the
blocked CI repair. Explicit workflow-maintenance issuance is separate from
unchanged ordinary-source tokens; no selected repository, model, public hosting
or runtime activation is granted.

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

Prepare a separate `prototype-source-authoring-v1` deployment profile using the
existing local model/binding, limits, route and bounded source change-set wire.
The native resolver requires a profile's callers to share its exact task set;
a separate existing-style profile preserves Delivery/Prototype caller isolation
without changing that resolver or broadening Delivery purpose. The proposed
source selection is now active like the existing source-realization deployment
configuration; baseline review remains only an anchor, not its live authority.
Do not load or deploy it before fresh exact composed Security acceptance and
explicit gateway commissioning. Keep Platform primary and running gateway at
their accepted configuration until that decision; other source-only producers
may align inside the announced merge window. No new model or download is needed.

Separate fixed App ownership from the personal and approved organization
installation accounts. Extend the existing Console canonical record reader
with immutable same-commit Inventory/Intake reads and reviewed-schema lookup;
the shared issuer takes this internal trusted reader without importing product
runtime code or accepting HTTP-selected authority. Legacy owners retain their
provider IDs. New ordinary owners require active Inventory, exact provider
coordinates and canonical promotion lineage; installation alone is insufficient.
Native contract inspection caught an incorrect staged coexistence requirement:
the actual owner promotion atomically removes Intake and retains its id,
version and digest in active Inventory. Correct both consumers and use actual
promotion output in their tests. Do not resurrect Intake or add a runtime proof
mechanism; current canonical Inventory is the owning admission authority.
Retired/suspended or duplicate bindings fail closed, including a fresh recheck
after custody preflight immediately before minting. Retained exact revocation
does not depend on current Inventory availability. The legacy engineering
delivery surface remains digest-pinned. Proposed trusted bootstrap, consumer
adapters and final coherent commissioning are still pending, not implied here.

The proposed-owner source primitive is now staged as a separate
`trusted-owner-bootstrap` purpose and real `repository-bootstrap` subject,
without changing ordinary Delivery/Prototype acceptance. The authenticated
provider uses the existing issuer/projection/recovery transaction; it does not
add an engineering CLI mint override. It independently validates current
canonical proposed source-only Intake, absent active/retired Inventory, exact
entry version/digest/provider coordinates, finite owner-control paths and
operator decision. Recheck follows custody preflight before the actual mint.
The credential projection and receipt are purpose-marked. Optional workflow
permission requires the selected workflow path and separate approval; ordinary
bootstrap without CI still receives four permissions. No model writes,
application import, checkout, admission or runtime authority is granted.
Actual loopback issuer tests cover the new purpose and ordinary regression
boundary (37 source-intent cases); this is not a real target token issuance or
Console operating witness. Remaining source consumers and exact Security
acceptance must be completed before activation.

## Artifact And Deployment Evidence

Final composition reuses the existing exact-source acceptance set for the
changed CGG context producer as well as the six prior implementation owners.
The existing lifecycle-context source boundary now selects actual merged CGG
`f80c06d9ece3b8706211c0be536407e610ef13e0`, without relaxing its exact rule.
Its older Security reference remains an architecture anchor, not acceptance of
this new source. The final composed decision must explicitly bind all seven
implementation owners and the actual Platform tree. No new activation manifest,
identity, source-purpose grant or ART child is introduced. Missing CGG binding
fails the existing policy validator before activation; prior accepted runtime
and new-purpose suspension are preserved until coherent reacceptance.

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
Fresh authorization of unchanged, still-valid work retains its canonical start
digest and session; expiry alone does not force source or branch churn. This
corrects a pre-activation restriction in the staged implementation. The new
intent still requires explicit approval and a fully revoked exact predecessor;
old commands remain isolated from the successor.

## Live Verification

- October20 actual Console source-scope preparation failed403 with
  `prototype_source_authoring_identity_forbidden` after full runtime recovery.
  Protected live comparison proved source work and Agent Console bind the
  caller to `operator:mfshaf7`, while Platform Operations, Publication and the
  session principal still used the generic `operator:workspace-owner`.
  Align the existing five current policies and compare them before effects;
  preserve roles, permissions, caller set and historical receipts. Rebind only
  the already-commissioned Publication Console entry, preserving other callers
  and its enabled posture. Readiness must verify boolean matches for all four
  live OOS maps. Preserve the original prepared c2aef request and its actor;
  no source intent, credential or session had been issued. Native positive and
  wrong-operator/missing-map denial, exact source review/Security acceptance
  and same-request actual Console proof remain required. No authorization
  guard weakening, aliases, model invocation or new identity subsystem.

- October20 post-reboot provider drift: actual configured Ollama metadata now
  reports0.40.6; the selected qwen3:8b digest500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
  is unchanged. Gateway correctly rejects the old0.40.5 binding. Align all six
  existing bindings to that installed physical runtime patch; retain model,
  purpose/caller/route grants, concurrency, budgets, exact-version/digest guards
  and frozen synthetic unit fixtures. No inference, download, model switch,
  host update policy change or crash-resolution claim. Existing failed
  auto-resume is stopped while source is reconciled. Native source tests,
  actual metadata-only adapter proof, exact composed Security reacceptance and
  normal activation remain required before live recovery is declared complete.

Public provider metadata confirms the newly approved App permission. Installation
acceptance and exact one-repository workflow-token readback are separate issuance
checks, not inferred from that metadata. Source tests cover ordinary permission
preservation, missing approval/grant denial, purpose isolation, exact approval
binding, secret-free receipts and normal revocation. The shared read-only provider
verifier remains unchanged. This is source preparation, not runtime activation.

Sandbox proof exercises the real issuer against loopback provider HTTP, private
projection, actual authenticated Platform API, replay/cold reconstruction,
concurrency, expiry/renewal, revocation and scope denials. This is engineering
evidence, not Console-operated credentials, to-do generation or Epic acceptance.
No live credential automation has been activated.
The actual issuer suite includes unchanged-session reauthorization after exact
revocation (22cases); OOS independently proves expiry stops automatic action and
fresh explicit successor adoption preserves the real session. Full committed
CI-equivalent evidence must be rerun for the revised staged head before merge.

## Follow-Up

Finish dependent OOS/Console authorization and source action guards; prepare
remaining owner contracts/consumers; acquire final exact composed Security delta
acceptance and generated Security record index after owner source lands; then
commission coherently and obtain the real Console operating witness. Existing
Studio/WG merge hold remains in effect. Source publishing/credential revocation,
open-PR custody and final branch retirement follow the existing normal path.
