---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime, ai]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_release_dispatch.py
    - products/governance-operations-console/scripts/console_release_identity.py
    - products/governance-operations-console/scripts/platform_operation_provider.py
    - products/openclaw/scripts/console_release_workflow.py
    - security/governed-release-identity.yaml
    - products/governance-operations-console/scripts/console_release_source.py
    - products/governance-operations-console/scripts/test_console_release_source.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/complete-runtime-policy.yaml
    - scripts/repository_provider_identity.py
    - .github/workflows/confirm-stage-promotion-readiness.yaml
    - .github/workflows/promote-environment.yaml
    - .github/workflows/manage-prod-environment.yaml
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console profile and governed-release integration

## Summary

Supply bounded owner records and native workflow entry for Dev Integration and
Governed Releases through the existing authenticated Platform provider. Profile
controls remain finite; native release submission uses its dedicated identity
and existing protected GitHub approvals. Source evidence and observed health
retain independent meaning.

## Classification

- Area: Console profile integration maintenance, explicitly operator approved.
- Landing Unit: `maintenance-dev-integration-profile-platform`.
- Landing Unit decision: `child_isolated_landing_unit`; separate runtime owner,
  exact-source Security review, validation and rollback boundary.
- Runtime impact: source staged; no live configuration or activation change.

## Ownership

Platform owns the safe projection and runtime effects. Workspace Governance owns
profile registry/admission. OOS owns canonical request mutation. Console consumes
the authenticated OOS APIs; it does not read host files or execute commands.

## Root Cause

The existing provider publishes one profile's finite controls, not a complete
profile register or the declared contract and evidence used by the Console views.

## Source Changes

Implemented in pending source: bounded committed-owner reads and source identity
through the existing provider. Unknown runtime/support evidence stays unknown.
List reads do not run per-profile status/smoke commands. Preserve existing profile
controls and the exact-source Security gate; the approved native release extension
below adds only the dedicated finite owner-workflow adapter.

## Local Validation

All 21 profile-reader and provider tests pass. The composed source proof reads
the actual seven-profile committed registry through the OOS/Console contracts.
Absent owner evidence remains unknown; list reads execute no runtime commands.

## Artifact And Deployment Evidence

None. Source tests do not authorize runtime activation.

## Live Verification

Pending. Qualification must cover safe current registry data, on-demand detail,
source drift, absent owner evidence, denied caller and absence of list side effects.

## Follow-Up Actions

Review the exact source delta, compose compatible OOS/Console sources through the
existing complete-runtime procedure and retain native operating evidence. Rollback
retains canonical requests and prior operation receipts.

## Governed Releases readback extension

The operator approved this surface's inspected repairs within the same pending
batch. Extend the existing authenticated provider with bounded committed product
registry/release reads. Unsupported products remain visible. The OpenClaw adapter
reads existing candidate, stage verification, readiness, production verification
and runtime-state records at one exact Platform revision. Those are recorded
contracts, not current observed health or executable Console progress.

Expose only validated links to existing protected Platform GitHub workflows.
Opening them creates no request, release command, approval or receipt. The later approved native extension below adds finite dispatch authority;
no shared component or live stage/prod state is changed. A product's stage/prod support remains independent
from Console adapter availability. Existing unsupported owner-managed products
are not forced into an OpenClaw workflow.

Local proof covers bounded pages/filters, source drift and target mismatch,
actual committed registry readback through both public DTOs, and zero runtime
commands during list reads. Exact-source Security review and the existing
complete-runtime composition/commissioning remain required before activation.
This remains the same owner/review/rollback Landing Unit and is uncommitted.

## Approved native governed-release extension

Operator approval `operator-approved:governed-release-native-20261102` extends this
same pending owner Landing Unit. Reuse existing Console/OOS/Platform operations,
private journals, protected owner workflows and their human approvals. No new ART
child, service, database or executor. The dedicated default-off App/Vault custody
is separate from Gary and other workflow identities. No live connection is
created or commissioned in this source work.

Commands bind exact source, actor, inputs and explicit approval. The owner writes
before dispatch and never automatically repeats an uncertain original. A valid
pre-dispatch rejection retains a no-effect receipt. Existing protected workflows
validate native App/source/input binding, safely pass user text as environment
values, push an original branch without force and open its PR. Source completion
requires actual merge ancestry and exact owner desired-state readback; runtime
health, smoke/UAT and readiness acceptance stay distinct. Terminal receipts are
immutable; failures with retained branches stay recoverable. Cancelling the
original run does not prove rollback.

The Console reuses release Details/Review and original operation history. Product
and executable capability must both be current. Its opaque recovery pointer does
not replace canonical journals; lost replies recover the exact original operation.
Unknown/live-source outages never substitute synthetic fixtures.

Source validation includes Platform native recovery/custody and existing provider
checks, strict OOS/Console DTOs, and isolated authenticated Console → OOS →
Platform browser qualification with synthetic GitHub transport. The exercise
proves one dispatch despite a lost reply, separate approval/review waits, merged
readback and cold OOS recovery. It performs zero live release writes and is not
operating acceptance. Preserve final owner CI-equivalent/source review evidence
before later publication. Security source delta:
[review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-02-console-native-governed-release.md).

After source landing, the existing exact-composition Platform/Security process
must bind the reviewed source and commissioned App before native availability.
Rollback withdraws native selection/credentials while preserving original owner
operations, source branches and receipts. Merge order for this pending extension:
Security evidence/index, Platform provider/workflows, OOS contract/API, Console.
All source remains uncommitted for the requested coherent batch review.

## Repeat-use source/data coherence

Final repeat-use inspection found that a completed GitHub merge would leave the
pinned local record reader behind owner main and prevent the next operation.
Keep reviewed runtime code pinned. The Platform-owned reader follows only fixed
owner GitOps records after complete non-record tree equivalence and ancestry
proof, using the existing dedicated App's read scope. It does not update a local
checkout, execute fetched code or move canonical data. Non-record source changes
still require the existing source acceptance. Snapshots retain explicit current,
accepted or retained posture; only verified owner main enables a native command.

A bounded private derived cache survives restart; immutable blob reuse and shared
head proof avoid repeated whole-source reads. Unknown source cannot become
current by refreshing the UI. Readiness-input failure does not remove an otherwise
valid runtime capability. The source tests and authenticated isolated browser path
now prove two consecutive merged operations with different owner-data revisions
and the same accepted runtime-code revision. No live release is dispatched.

## Live publication binding correction

The source review and first managed activation completed, but native Console
readback returned `dev_integration_not_configured`: the two intentionally default-off
OOS integration flags were absent from the managed binding. The core readiness
check did not cover them. Bind the profile/product flags with the existing
canonical-record flags on both activation and restart, verify consumed state, and
disable/remove them through existing rollback. No new service, command family,
identity or App commissioning is introduced. Existing lifecycle regressions cover
both disabled flags and rollback; live read-only profile/product proof remains
required after the corrected source is accepted and restarted.
