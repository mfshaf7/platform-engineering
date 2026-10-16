---
security_evidence:
  review_areas: [identity, secrets, runtime, delivery]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_workflow_credentials.py
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: Reconcile existing OOS registry caller consumption only; separate GitHub identities, permissions and source gates remain unchanged.
---

# Prototype readiness caller reconciliation

## Summary

- Date: 2026-10-16
- Short title: maintain current WGCF caller bindings for all three Prototype workflows
- Environment: local dev-integration
- Severity: real Console Landing readiness authentication blocked

## Classification

- Type: environment credential drift and incomplete runtime reconciliation
- User-facing impact: Landing accepted setup but could not evaluate readiness; provider token health concealed stale readiness caller credentials.

## Ownership

- Owning repo or layer: platform-engineering
- Related repos: security-architecture, operator-orchestration-service, workspace-governance-control-fabric
- Related ADR: existing dedicated Prototype identities; no new identity or service

## Root Cause

- Immediate failure: actual Console Landing continuation returned WGCF401 before source publication.
- Actual root cause: Landing, Maturity and Closure retained old caller credentials and historical issuer expectations while the active WGCF registry used the current composition-owned OOS credential and reviewed image revision. Renewal preserved these stale fields and verified only GitHub provider access.
- Why it escaped earlier controls: primary register reads and valid installation tokens do not exercise WGCF readiness authentication.

## Source Changes

- Repo: platform-engineering
- Commit(s): Landing Unit maintenance-1275-readiness-callers-platform; exact Gary commit/PR in source delivery receipt.
- Guardrail added: exact current WGCF session, principal, Secret source and consumed reviewed-image proof; reconcile only declared owner keys and bind consumer issuer refs to the Security-accepted WGCF revision; CAS/original SSA ownership; caller-only versioned consumption without token mint; grouped authenticated read-only readiness checks; positive, negative and interruption tests. OOS exact issuer checks remain unchanged.

## Artifact And Deployment Evidence

- Build workflow run: required Platform CI and committed-head local make validate before merge.
- Published image tag: None; existing Platform host coordinator
- Published digest: exact reviewed Platform tree in composed Security decision
- Recorded prod revision: None; local dev-integration only
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: normal accepted complete-runtime activation and existing credential refresh after exact Security acceptance.
- Why it was environment drift instead of source defect: stale caller values were drift; preserving them indefinitely and claiming health without readiness authentication was a Platform implementation gap.
- Recovery command or procedure: existing governance-console-complete-runtime activate/status/refresh-credentials. Preserve and resume the original Proposal1305 Landing request, never recreate the product or bypass WGCF.

## Live Verification

- App health: requires actual all-three-family readiness-authentication proof after commissioning, separately from provider token validity.
- Deployed image: unchanged OOS and WGCF reviewed images
- Pod: current admitted owner deployments, discovered at verification
- Functional verification: same Console Landing request must advance through readiness/source review; no claim of to-do generation or Epic completion from health checks.
- Residual risk: source generation and packet-authoring gaps remain separate accepted journey work; this repair does not widen their activation.

## Follow-Up

- Required follow-up: exact Security/index acceptance, ordered activation, actual caller consumption proof, same-request Console continuation and source-resource retirement.
- Optional hardening: None; reuse the current timer and caller principal.
- Owner: platform-engineering
