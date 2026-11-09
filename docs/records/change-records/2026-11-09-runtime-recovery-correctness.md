---
security_evidence:
  review_areas: [runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Interrupted runtime recovery correctness

## Summary

- Date: 2026-11-09.
- Classification: operator-authorized Platform owner maintenance outside ART.
- Landing Unit Decision: `feature_single_landing_unit`,
  `runtime-recovery-correctness-20261109`.
- Posture: extend the existing finite image checker and consumer lifecycle.

## Classification

Repair existing recovery behavior exposed by interrupted local operation. This
does not create an initiative, service, registry, caller permission or generic
file-overwrite facility. The unpublished editor maintenance remains separate.

## Ownership

Platform owns the root helper, image-cache recovery and retained lifecycle.
Security owns exact-source acceptance. Existing backend owners retain database,
project, workflow and source authority.

## Root Cause

Interrupted checks left verifier-owned read views retaining image snapshots.
Archive import generated temporary repository names which remained in native
image metadata and the CRI index. Removed images could disappear from coverage
when another digest of the same repository remained. A maintenance tick could
replace a pending-recovery journal and discard original consumer state.

These are software recovery defects. Native process crashes and changing image
bytes were also observed; their physical cause remains unproven. Neither the
source repair nor a successful scan establishes hardware reliability.

## Source Changes

The maintenance candidate preserves each unresolved immutable image, imports
under its admitted repository, retains recovery journals through maintenance,
and reclaims only proven pre-boot, unmounted verifier read views. Unknown imports,
foreign resources, live mounts, mutable data and one-attempt guards remain
protected. Pending-recovery ticks do not start another scan or overwrite the
journal; ordinary unknown-fault transitions retain existing evidence. Historical
temporary image identities still require operator inspection, not silent
identity rewriting. No automatic program-file overwrite is added.

Thirty-six focused tests pass, including same-repository missing-image coverage,
uncertain-import refusal, canonical import arguments, pending journal retention,
and current/live/foreign/nonempty/symlink read-view denials. A native import of
the exact retained PostgreSQL archive in a separate temporary metadata namespace
produced only the canonical admitted name. That proof did not unpack images or
run workloads, and its temporary namespace was removed. Full CI-equivalent
validation and exact Security acceptance remain required before commissioning.

## Artifact And Deployment Evidence

The existing [archive recovery review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-08-image-recovery-archives.md)
is the baseline; a fresh delta and exact merged-source acceptance are required
before deliberate root-helper installation and normal activation. Source
checks alone do not commission the candidate.

## Live Verification

Manual recovery evidence is retained in operator-private custody. The earlier
helper remains installed while this candidate is prepared. Final source,
helper hashes, native import names, consumer readiness and cleanup evidence
must be recorded before operational completion is claimed.

## Follow-Up Actions

Complete focused adverse-state and CI-equivalent proof, Gary publication,
delegated human review and merge, the dependent Security index/acceptance,
reviewed installation, native owner readback and source-resource cleanup.
Rollback retains the previous accepted source/helper, archives and journals;
it never resets mutable project data or erases failed-attempt evidence.
