---
security_evidence:
  review_areas: [delivery, runtime]
  reviewed_artifacts:
    - scripts/dev_integration_compositions.py
    - scripts/test_dev_integration_compositions.py
    - docs/runbooks/dev-integration-profiles.md
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Composition status recovery

## Summary

Restore truthful aggregate health after a transient profile failure recovers,
while preserving incomplete startup/shutdown and suspended-state boundaries.

## Classification

Operator-authorized shared runtime maintenance. Landing Unit decision:
`feature_single_landing_unit`, `maintenance-composition-status-recovery`.
No new ART item, service, command, approval path or architecture version.

## Ownership

Platform owns the shared runner, private composition record and primary
[operator procedure](../../runbooks/dev-integration-profiles.md#composition-health-after-recovery).
Workspace Governance owns composition topology/admission; profile owners retain
their readiness semantics. Security owns the
[scoped review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/platform/2026-11-03-composition-status-recovery.md).

## Root Cause

A background delivery projection failed, then its normal retry succeeded.
Subsequent composed checks passed every participant with no failed profile,
but status copied the earlier degraded lifecycle label. The record also lost
the distinction between a health-check failure and an incomplete explicit
startup/shutdown. Returning every healthy observation to active would therefore
be unsafe after a failed lifecycle operation.

## Source Changes

Retain the last explicit lifecycle result in the existing private record.
Persist incomplete intent before profile calls, and retain failure if an action
is interrupted. After all status checks pass, restore active only from a known
completed startup. Failed, interrupted, suspended, unknown and ambiguous legacy
state cannot acquire active context from health observations alone. Preserve
existing credentials and ownership checks. Short metadata locks and a fresh
read protect newer lifecycle intent from a status call started earlier.

## Artifact And Deployment Evidence

Source candidate. Publish through Gary and delegated accountable review; final
Console composition acceptance must select the reviewed Platform source/tree
before normal activation. The generated Security index follows the merged
owner record. No manual live-state rewrite is part of this change.

## Live Verification

The native pre-fix record showed all five profile checks passing, no failed
profile, a successful complete-runtime status and a retained degraded label.
Regression qualification covers recovery with unchanged credentials, partial
failure, failed/interrupted startup and shutdown, status overlapping a new
lifecycle intent, suspended/unknown/legacy state and missing record denial.
Final reviewed-source activation and current composed status remain required.

## Follow-Up

Land reviewed source, update exact composed acceptance and generated Security
index, then verify the normal runtime producer reports current health. Preserve
profile-owned retry behavior and owner data. Roll back through the prior
accepted Platform source and matching Security decision; do not edit the live
label or disable readiness checks.
