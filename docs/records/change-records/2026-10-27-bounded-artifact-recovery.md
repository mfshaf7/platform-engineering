---
security_evidence:
  review_areas: [runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Bounded Console artifact recovery

## Summary

Extend existing Platform lifecycle to check immutable runtime bytes and restore
exact approved artifacts without resetting data. The operator accepts imperfect
RAM and explicitly authorized implementation.

## Classification

Owner maintenance linked to the existing accepted Console memory candidate and
workspace-governance PR314; no new ART item. Landing Unit Decision:
feature_single_landing_unit; maintenance-artifact-integrity-recovery. Shared
checker and Console adapter share review/activation/rollback; Security acceptance
is a separate dependent owner landing.

## Ownership

Platform owns implementation and finite root installation. Security owns the
fresh host/runtime delta and exact execution-tree acceptance. Gary authors;
mfshaf7 retains delegated review/merge. No model/browser gets root arguments or
containerd socket access.

## Root Cause

Unpacked PostgreSQL readiness code differed by one bit from verified same-image
bytes while compressed layers and relevant Git blobs were intact. The broader
audit found two further cached-tool hash mismatches. Hardware diagnosis is not a
prerequisite; imperfect RAM is the accepted constraint.

## Source Changes

Digest-verified OCI inventories, read-only filesystem checking, bounded native
cache refresh, shared-consumer quiescence/owner-operation exclusion, durable
attempt latches, existing-timer detection, retained-supervisor resume and derived
frontend rebuild. See [ADR-031](../../decisions/adr/ADR-031-bounded-local-artifact-recovery.md)
and the [operator procedure](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).

## Artifact And Deployment Evidence

Staged source requires exact checks and fresh Security acceptance before root
installation or activation. Dev-integration only; consumed immutable versions
are preserved. Final source/operating evidence stays in the existing recovery
candidate; this record needs no post-review source-pin rewrite.

## Live Verification

Earlier targeted PostgreSQL refresh and full Console/history proof passed. The
new independent checker matched3,862 PostgreSQL entries and found the wider
cached-tool mismatches. Controlled failure/repair and automatic operating proof
must be recorded separately; source tests alone do not establish that outcome.

## Follow-Up

Require exact Security acceptance, full local/hosted validation, helper attestation,
corruption/denial proof and native automatic recovery with original owner
data/history preserved. Keep the same candidate accepted until that proof.
No generic source/database/credential restoration is authorized.
