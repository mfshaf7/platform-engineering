---
security_evidence:
  review_areas: [identity, runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console Journey Records and Realization

## Summary

- Date: 2026-10-16
- Short title: Complete the existing live Console journey composition
- Environment: local `dev-integration` only
- Severity: Existing acceptance remains blocked pending operating proof

## Classification

- Type: Product runtime composition and existing governed model integration
- Landing Unit: `maintenance-1275-console-journey-platform`
- Landing Unit Decision: `child_isolated_landing_unit`; Platform has its own
  source, review, deployment and rollback boundary in the operator-approved
  coherent maintenance batch. No new ART child is created.
- User-facing impact: Prototype and Delivery primary reads, record freshness,
  Preview and source-realization commissioning share one existing lifecycle.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: Console, OOS, WGCF, Workspace Governance, Prototype Studio
  and Security Architecture
- Related ADR: ADR-020 declared host services and ADR-021 multi-profile
  governed AI gateway; this extends existing owners, not a new control plane.

## Root Cause

- Immediate failure: Primary live Console registers and realization interaction
  were not fully wired, and their existing dependencies were not commissioned.
- Actual root cause: Earlier capability proof established adapters and fixture
  denial without proving the whole operator journey. Fixed reviewed control
  code was conflated with changing canonical business records. Generic startup
  could restore only the raw profile instead of the complete composition.
- Why it escaped earlier controls: Source, contract, runtime and demonstrated
  operating readiness were treated as interchangeable. The real fixture-free
  acceptance exposed the missing seams. A separate observed web-service exit
  was reported as successful, so failure-only restart left the UI down.
  Damaged webpack cache entries were observed and moved aside recoverably;
  their causal role in that process exit is not established.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): This maintenance Landing Unit; exact source and merge evidence
  are retained by its Gary-authored pull request, not invented in advance.
- Guardrail added:
  - Native bounded private Git snapshot/checkpoint producer; only approved
    canonical records may advance while execution code and policy stay pinned.
  - Existing timer refreshes records every minute without skipping credential
    renewal on data failure; expired checkpoints withhold writes.
  - Actual read-only workload mount, flag and consumed-generation checks;
    successful live Prototype and Delivery primary models are required.
  - Existing Ollama-backed source-realization profile, exact gateway caller
    and structural provider schema; OOS semantic validation is independent.
  - Existing Studio Preview adapter receives reviewed control plus fresh record
    identity, never arbitrary source or browser execution authority.
  - Normal activation and Platform start reuse the existing retained
    composition oneshot via a product-owned drop-in; no new service family.
  - Full uncached proof rejects temporary supervision before effects.
  - Console service restart also covers unexpected successful process exit.
  - Current Security decisions are always validated; unrelated generated-index
    commits do not change the relevant decision's provenance anchor.
  - Rollback restores primary mounts, disables new flags, removes only the
    product drop-in and preserves canonical history and cached unique work.

## Artifact And Deployment Evidence

- Build workflow run: Required exact-head Platform CI; not yet operating proof.
- Published image tag: None; existing composition builds its admitted sources.
- Published digest: Not applicable to this source-only record.
- Recorded prod revision: None; stage and production are outside scope.
- Argo application revision: None; local `dev-integration` only.
- Merge order: OOS and WGCF, Console, Platform, Workspace Governance final
  guidance, then final Security acceptance/index and coordinated activation.
- Exact-revision consumers: Existing complete-runtime Security decision and
  private resolved policy, runtime images, composition manifest and retained
  startup units require ordered refresh. Primary checkouts remain at the prior
  accepted revisions until the complete source batch is ready.

## Host Or Runtime Recovery

- Required host/runtime action: Activate through the existing complete-runtime
  command after exact Security acceptance, then prove after controller exit.
- Why it was environment drift instead of source defect: The cache is generated
  local state; missing live bindings and composition are source omissions, not
  an inferred host or memory defect. No host tuning or new daemon is included.
- Recovery command or procedure: The existing complete-runtime runbook is the
  primary surface; rollback preserves owner data and the generic profile unit.

## Live Verification

- App health: Temporary homepage success is not durable availability proof.
- Deployed image: New coordinated runtime not yet activated by this record.
- Pod: Determined from the admitted composition during operating verification.
- Functional verification: Native producer and actual-image reader engineering
  proof do not replace the real Console journey. Preserve idea 1305 and its
  repository/capture. Use Prototype exploration and its canonical Delivery
  handoff, then Delivery Work Design and its governed source work session.
  No hidden Codex/CLI to-do implementation is permitted.
- Residual risk: The app is not built yet. Add, complete, delete, reload
  persistence, real source, local preview and Portfolio readback remain the
  existing acceptance obligation.

## Follow-Up

- Required follow-up: Exact-head owner validation, Security review/index,
  retained runtime commissioning and the real Console-created to-do journey.
- Optional hardening: None invented for this maintenance batch.
- Owner: Platform Engineering; existing acceptance item 1298 retains the
  cross-owner demonstrated outcome.
