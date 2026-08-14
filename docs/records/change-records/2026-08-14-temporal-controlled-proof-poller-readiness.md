# Temporal Controlled-Proof Poller Readiness

## Summary

- Date: 2026-08-14
- Short title: Prove admitted Temporal pollers before commissioning
- Environment: `dev-integration`
- Severity: commissioning blocker

## Classification

- Type: deployment and operator-runtime defect
- User-facing impact: ART #751 cannot produce trustworthy commissioning
  evidence until the runtime proves its worker pollers and retains bounded
  request-failure evidence.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`,
  `workspace-governance-control-fabric`
- Related ADR:
  [ADR-018](../../decisions/adr/ADR-018-permit-gated-component-commissioning-proof.md)

## Root Cause

- Immediate failure: the first controlled-proof execution was accepted, but
  its first retained read timed out and became `scenario-executor-failed`.
- Actual root cause: Platform waited for Kubernetes Deployments, not the exact
  OOS workflow and WGCF activity pollers on their admitted Temporal task
  queues. A worker-registration race therefore remained open.
- Why it escaped earlier controls: owner-level tests proved workflow and
  activity contracts without exercising the assembled-runtime interval between
  Deployment readiness and Temporal poller registration. The HTTP adapter also
  discarded bounded failure context.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): this ART #837 landing unit; the finalized Review Packet records
  the exact merged commit.
- Guardrail added:
  - wait for the exact admitted workflow and activity poller identities
  - reject unexpected identities on either pinned task queue
  - retain redacted HTTP, transport, and invalid-response failure evidence
  - test absent and delayed readiness, unexpected identity, and redacted HTTP
    evidence
  - document immediate post-approval execution without an idle time buffer

## Artifact And Deployment Evidence

- Build workflow run: pending source landing
- Published image tag: None; Platform executor source only
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: None; the failed session completed exact
  baseline restoration and removed its operator-scoped runtime.
- Why it was environment drift instead of source defect: None; this was a
  source-level readiness and evidence-custody defect.
- Recovery command or procedure: obtain a fresh permit after ART #837 lands;
  the consumed permit must not be reused.

## Live Verification

- App health: the failed session installed the bounded runtime successfully;
  exact baseline restoration passed.
- Deployed image: the failed session used the permit-pinned OOS and WGCF image
  digests recorded in its immutable authorization.
- Pod: no proof Pod remains after exact restoration.
- Functional verification: an isolated synthetic reproduction against the
  exact pinned OOS images proved that start and retained read succeed with the
  workflow poller registered, while the same read times out when no workflow
  poller is registered.
- Residual risk: the full eleven-scenario session still requires a fresh
  authorization and rerun after this source correction lands.

## Follow-Up

- Required follow-up: merge ART #837, finalize its Review Packet, issue a fresh
  Security- and operator-approved permit, and rerun ART #751.
- Optional hardening: None before the fresh run; use its bounded evidence to
  classify any new failure rather than expanding this correction speculatively.
- Owner: Platform Engineering
