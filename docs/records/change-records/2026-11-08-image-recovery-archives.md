---
security_evidence:
  review_areas: [runtime, secrets, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Verified local image recovery archives

## Summary

- Date: 2026-11-08.
- Classification: operator-approved owner maintenance in local dev-integration.
- Landing Unit Decision: `feature_single_landing_unit`,
  `maintenance-image-recovery-archives-20261108`.
- Owner: Platform Engineering; existing finite image recovery and Console lifecycle.

## Classification

Maintenance for deployment/cache recovery in the existing local lane. No ART item,
production release, new subsystem or accepted-risk waiver is created.

## Ownership

Platform owns the finite root helper, archive custody and consumer lifecycle.
Security owns the exact source acceptance. Console and AI callers receive no new
host authority. Existing backend owners retain project data and workflow truth.

## Root Cause

Publication of Console PR171 exposed a changed MinIO executable in an unpacked
runtime image. The verifier detected its exact checksum mismatch. Automatic
replacement then removed the damaged cache and failed to pull the original
immutable image because its upstream repository denied access. The verifier
correctly withheld successful activation; the replacement procedure still
depended on upstream availability after its destructive boundary.

Delegated operator recovery obtained the identical approved image digest from a
mirror, restored original aliases and passed an independent 18-image check.
A later scan found a different mismatch in Temporal admin-tools. The outer
single-recovery guard treated that new artifact as an attempt to replay the
earlier recovery, although the root incidents already provide per-image limits.
The physical cause of either byte mismatch is unproven. Neither mismatch is
evidence of a defect in Console source or loss of mutable project records.

## Source Changes

The root helper now exports and verifies original compressed OCI content before
removing damaged cache metadata. It validates the admitted reference, selected
platform, descriptor graph, blob hashes and sizes without extracting archive
paths. Replacement uses that retained archive and verifies the resulting files;
it does not depend on a later upstream pull. Retained archives also supply fresh
trusted baselines when native compressed blobs are unavailable, preserving the
original descriptor checks. Invalid or missing original content
blocks before removal. Uncertain import and failed verification retain their
incident rather than being retried indefinitely.

An exact interrupted replacement can finish its one not-yet-started archive
import. A distinct damaged image can proceed while prior verified replacements
await consumer readiness, preserving original controller identities, desired
replicas and all recovery evidence. Existing root incidents retain one attempt
per image. No new registry, service, credentials, namespaces or model/Console
host-control permission is introduced. Mutable data volumes are untouched.

## Validation

Owner CI-equivalent validation includes the new faithful OCI archive and
upstream-denial cases in `make validate`, alongside existing integrity and
consumer-recovery tests. The source candidate verifier also accepts a real
export of the exact approved MinIO OCI graph. Full owner validation, exact-head
CI, fresh Security acceptance and native commissioning remain required before
reporting this source change operational.

## Artifact And Deployment Evidence

The fresh [Security delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-08-image-recovery-archives.md)
must bind the validated Platform tree and current Console composition through
the existing finite decision. Reinstall the root helper deliberately only after
that acceptance, then use normal activation and owner readback. Keep the prior
source/decision and all journals and archives for the existing rollback and
operator inspection path. The primary procedure is
[Operate the complete runtime](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md#verified-local-image-archives).

## Live Verification

This record describes source intent and validation, not completed commissioning.
Exact merged commits, accepted helper hashes, real recovery, native Console
reads, credential revocation and branch cleanup belong in the private execution
receipt and final operator report after they are proven. Generated Security
source-record indexing follows owner source merge, avoiding circular evidence.

## Follow-Up

Complete exact-source review and commissioning, then prove the real damaged-image
recovery and healthy consumers. Preserve original audit records, revoke both
publication credentials and retire the completed source resources. Source tests
and retained archives do not prove future hardware faults are recoverable.
