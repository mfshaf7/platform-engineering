---
security_evidence:
  review_areas: [runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Verify program-cache rereads before image replacement

## Summary

- Date: 2026-11-09.
- Classification: operator-authorized runtime recovery maintenance outside ART.
- Landing Unit Decision: `feature_single_landing_unit`,
  `runtime-cache-readback-20261109`.
- Posture: extend the existing finite image verifier and maintenance path.

## Classification

Correct the existing comparison before destructive derived-cache recovery.
This introduces no service, caller, repository, namespace or data authority.
The unpublished editor batch remains separate.

## Ownership

Platform owns image comparison and runtime recovery. Security owns exact-source
acceptance. Backend owners retain project data, credentials and workflow truth.

## Root Cause

Previously verified PostgreSQL and OpenProject program files later read different
bytes. Targeted cache advice temporarily restored trusted reads, but incorrect
reads could recur through another mount. A one-time inspected clean page-cache
reset restored agreement between Python, an independent checksum tool and the
verified image hashes in a new process. No program-file replacement was required.
This proves an unreliable cached-read case, not the physical cause of every
native crash or a guarantee of hardware reliability.

## Source Changes

On a regular-file hash mismatch, refresh the independently verified baseline,
then request a clean-cache reread through a read-only descriptor within the
existing image mount. Reject escaped paths and links. A successful read must
also survive a separate fresh native view. Otherwise the image remains corrupt;
unsupported advice, persistent bytes and recurring bad reads cannot become a
healthy result. Existing archive and uncertain-attempt guards remain unchanged.

Receipts retain cache-readback evidence. Cached confirmation requires identical
boot, helper, policy and image-set identity. Existing idle-checked maintenance
resumes its retained supervisor after proven cache recovery without image
replacement. The helper gains no global cache reset or program-file write.

## Artifact And Deployment Evidence

Forty-three focused integrity/archive/consumer tests cover read-only descriptors,
fresh trusted bytes, persistent mismatch, unavailable advice, path/link refusal,
metadata-only changes, recurrence through another mount, proof version binding
and idle-checked supervisor resumption. Full exact-head provider checks, fresh
Security review and merged-source acceptance precede reviewed installation.

The baseline is the [interrupted recovery review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-09-runtime-recovery-correctness.md).
The new delta must bind the exact merged candidate before commissioning.

## Live Verification

Manual readback/reset evidence stays in operator-private custody. The existing
installed helper remains active until accepted installation. Source tests and
the manual cache recovery are distinct from an automatic-recovery witness;
native complete-runtime readiness remains required for operational completion.

## Follow-Up Actions

Complete Gary publication, delegated review, Security index/exact source
acceptance, reviewed installation and native readiness. Retire only this Landing
Unit's resources. Preserve original UI worktrees, archives, incidents, controller
identities and mutable project data. Rollback restores the previous accepted
source/helper without deleting evidence or resetting data.
