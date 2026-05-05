---
security_evidence:
  review_areas:
    - runtime
    - ai
    - delivery
  findings: []
  risks:
    - R-007
  workstreams:
    - WS-007
---

# CGG Dev-Integration Platform Activation Acceptance

## Summary

- Date: 2026-05-05
- Short title: CGG dev-integration platform activation acceptance
- Environment: dev-integration
- Severity: normal platform enablement

## Classification

- Type: shared component dev-integration admission
- User-facing impact: operators can launch and inspect CGG through the shared
  `devint-*` runner after workspace lifecycle activation, instead of relying
  on direct owner-repo runtime overrides.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos:
  - `context-governance-gateway`
  - `workspace-governance`
  - `security-architecture`
- Related ADR: None

## Root Cause

- Immediate failure: CGG had service-mode source and owner-repo dev-integration
  scripts, but the platform docs still described the component as having no
  approved operational path.
- Actual root cause: build admission and implementation proof were not enough
  to make the profile operational; platform still needed to accept the
  concrete runtime shape, persistent storage behavior, access path, read-only
  smoke, suspend semantics, reset semantics, and stage handoff boundary.
- Why it escaped earlier controls: the earlier plan treated the dev-integration
  profile as a future owner-repo concern instead of requiring a platform
  acceptance record before workspace lifecycle activation.

## Runtime Decision

Platform accepts `context-governance-gateway` as a local-k3s
`dev-integration` runtime lane after workspace lifecycle activation.

The accepted day-one runtime is:

- one CGG API Deployment and ClusterIP Service
- one CGG worker Deployment
- one local PostgreSQL Deployment, Service, and PVC for dev-integration
  metadata hardening
- one local MinIO Deployment, Service, and PVC for dev-integration artifact
  custody hardening
- one PVC-backed CGG state volume for packets, receipts, manifests, redaction
  reports, raw artifacts, and ledger files
- owner-repo scripts for `devint-up`, `devint-status`, `devint-access`,
  `devint-smoke`, `devint-down`, `devint-reset`, and `devint-promote-check`
- read-only smoke on the persistent working lane
- `devint-down` suspend semantics that preserve PVCs and local secrets
- `devint-reset` destructive semantics for local CGG namespace and profile
  state
- no governed stage or production deployment approval
- no model-facing adapter approval

## Source Changes

- Repo: `platform-engineering`
- Commit(s):
  - `github://mfshaf7/platform-engineering/pull/187` for ART #636, #637,
    and #638
  - generated security index dependency:
    `github://mfshaf7/security-architecture/pull/80`
- Guardrail added:
  - platform component docs now describe the exact local dev-integration access
    and operation boundary
  - platform release-governance docs now separate dev-integration acceptance
    from governed stage and production approval
  - shared dev-integration runbook now lists CGG as platform-accepted pending
    active workspace lifecycle

## Artifact And Deployment Evidence

- Build workflow run: not applicable for documentation-only platform
  acceptance
- Published image tag: none
- Published digest: none
- Recorded prod revision: none
- Argo application revision: none

## Host Or Runtime Recovery

- Required host/runtime action: after workspace activation, run
  `make devint-up PROFILE=context-governance-gateway`.
- Why it was environment drift instead of source defect: None; this is platform
  acceptance of a new local dev-integration runtime lane.
- Recovery command or procedure:
  `make devint-down PROFILE=context-governance-gateway` suspends local runtime
  while preserving PVCs and local secrets. `make devint-reset
  PROFILE=context-governance-gateway` deletes the local namespace and local
  profile state.

## Live Verification

- App health: owner-repo active smoke passed before platform acceptance.
- Deployed image: none; day-one active dev-integration uses owner-repo source
  mounted into local-k3s runtime.
- Namespace: `devint-context-governance-gateway-<operator>` after workspace
  activation.
- Persistent storage evidence: owner-repo active proof showed PVC-backed CGG
  state, PostgreSQL data, and MinIO data.
- Functional verification:
  - owner-repo active smoke passed with API readiness, raw projection denial,
    redaction marker presence, receipt and manifest digest match, dashboard
    packet count, metrics, and trace metadata
  - shared runner remains lifecycle-gated by the workspace registry
  - build-admitted launch, access, and smoke continue to fail closed until
    active
- Residual risk: dev-integration remains local evidence only and must not be
  represented as governed stage or production readiness.

## Follow-Up

- Required follow-up: workspace governance must flip the profile lifecycle to
  `active` only after security review is refreshed and this platform acceptance
  is referenced.
- Optional hardening: add governed stage and production deployment only after
  image provenance, identity, secret delivery, backup, restore, retention,
  deletion, debug override, and security gates are recorded.
- Owner: `platform-engineering`
