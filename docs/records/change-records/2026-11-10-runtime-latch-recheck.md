---
security_evidence:
  review_areas: [runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Verified release of runtime check failures

## Summary

- Date: 2026-11-10.
- Short title: Verified release of runtime check failures
- Classification: operator-authorized Platform recovery maintenance outside ART.
- Landing Unit Decision: `feature_single_landing_unit`,
  `runtime-latch-recheck-20261110`.
- Posture: extend the existing finite integrity checker and retained supervisor.

## Classification

The operator approved this recovery improvement before returning to the shared
project-runtime initiative. It changes neither that initiative nor its ART tree.

## Ownership

Platform owns implementation and operation; Security owns the delta review and
exact-source acceptance. No new service, caller, root action or workflow is added.

## Root Cause

A virtual-disk read failure latched startup for operator inspection. After a
later reboot, all 18 admitted images verified healthy with no unresolved root
repair incident, but startup and maintenance still refused to recheck the latch.
An inspected manual transition and normal activation restored all 26 pods and
current Console owner records. This does not prove a physical disk failure or
hardware reliability. The former unconditional latch was deliberate protection;
the approved change narrows manual intervention only where fresh proof suffices.

## Source Changes

Only a failed integrity check entered from a healthy journal creates explicit
automatic verification eligibility. The existing startup and timer share one
persisted attempt per boot under the owner guard and respect active owner/Helm
work. No reason-string matching or migration of unknown historical latches is
used. The root checker reports still-open repair phases independently of healthy
bytes. Fresh accepted-helper coverage with no pending repair permits only a
transition to readiness pending; the normal owner/frontend checks and confirmation
remain mandatory. Journal evidence and replacement guards are preserved.

This path never invokes image replacement, repeats an import, stops consumers or
restarts K3s. Existing bounded inspection-view cleanup and proven absent-alias
reconciliation remain unchanged. The accepted policy can disable verification
resume. Mutable data, source, credentials, uncertain repair and unrelated owner
failures remain outside automatic release.

## Artifact And Deployment Evidence

Focused tests cover adverse proof, pending repairs, failed repair/frontend
exclusion, durable per-boot bounds, policy disable, owner contention, retained
supervisor use and readiness-gated confirmation. Full owner CI-equivalent checks,
Gary publication, delegated exact-head review and a dependent Security acceptance
are required before deliberate helper installation and native qualification.

Primary procedure: [Operate the complete runtime](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md#automatic-artifact-integrity-and-recovery).
Security baseline: [Interrupted runtime recovery review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-09-runtime-recovery-correctness.md).

## Live Verification

Native operating proof is retained privately with the maintenance evidence. A
controlled verification-unavailable case will exercise automatic recheck and
normal readiness without corrupting an image or business data. This is distinct
from a real power-loss or hardware-reliability claim. Source checks alone do not
establish automatic operating recovery.

## Follow-Up

Complete exact-head validation/review, source landing, dependent Security
acceptance and controlled native qualification before reporting completion.

Rollback restores the prior exact accepted Platform/helper/policy and Security
binding, preserving journals, archives, consumer evidence and application data.
Do not clear unknown latches or reclassify an uncertain repair as verification.
