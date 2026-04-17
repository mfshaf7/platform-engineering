# Change Record

## Summary

- Date: 2026-04-17
- Short title: Governed OpenClaw prod lifecycle drill validated `live`,
  `traffic-stopped`, `quarantined`, and return to `suspended`
- Environment: prod
- Severity: medium

## Classification

- Type: platform lifecycle control validation
- User-facing impact: deliberate, time-bounded OpenClaw prod state changes were
  used to validate the governed lifecycle behavior. Prod user traffic was
  intentionally restored, cut at the deployment boundary, quarantined, and then
  returned to the quieter suspended state.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `security-architecture`
- Related ADR:
  - `docs/decisions/adr/ADR-011-governed-runtime-lifecycle-standard.md`

## Root Cause

- Immediate failure: None. This was a deliberate governed lifecycle drill, not
  an incident response or defect repair.
- Actual root cause: None.
- Why it escaped earlier controls: Not applicable. The purpose of the drill was
  to validate the corrected traffic-stop abstraction after the lifecycle model
  moved from a Telegram-specific runtime gate to a platform-level deployment
  boundary control.

## Source Changes

- Repo: `platform-engineering`
- Commit(s):
  - lifecycle standard merge: `7bae3a20535d3d8ea42d6c47057d7cf59e8fe0de`
  - drill live: `594c47a09c2677d66972f61216a073d8cf742a64`
  - drill traffic-stopped: `6ca53e94bea56cd3ec0b7ac779badb4bd9b3c74b`
  - drill quarantined: `ed419905490f5e03dbf2865ce9af5568f87e8e7a`
  - return to suspended: `0c6ae3924a8500f9bfb3e0c3b24d028b89ce5540`
- Guardrail added:
  - shared runtime lifecycle standard in
    `docs/standards/governed-runtime-lifecycle-model.md`
  - ADR-011 documenting the corrected `traffic-stopped` abstraction
  - OpenClaw prod lifecycle controller and docs now treat `traffic-stopped` as
    deployment-level gateway removal with retained support surfaces
  - security review in
    `security-architecture/docs/reviews/products/2026-04-17-openclaw-governed-runtime-lifecycle-standard.md`

## Artifact And Deployment Evidence

- Build workflow run: none; the drill exercised lifecycle control only and did
  not build a new gateway image
- Published image tag: `gateway-1fb1b11b4142`
- Published digest:
  `sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Recorded prod revision:
  - `live`: `594c47a09c2677d66972f61216a073d8cf742a64`
  - `traffic-stopped`: `6ca53e94bea56cd3ec0b7ac779badb4bd9b3c74b`
  - `quarantined`: `ed419905490f5e03dbf2865ce9af5568f87e8e7a`
  - final `suspended`: `0c6ae3924a8500f9bfb3e0c3b24d028b89ce5540`
- Argo application revision:
  - `platform-root-prod` reconciled through the same sequence and finished on
    `0c6ae3924a8500f9bfb3e0c3b24d028b89ce5540`

## Host Or Runtime Recovery

- Required host/runtime action: None
- Why it was environment drift instead of source defect: Not applicable
- Recovery command or procedure: None

## Live Verification

- App health:
  - `platform-root-prod` stayed `Synced Healthy` through the drill
  - the expected OpenClaw prod child applications appeared or disappeared by
    lifecycle state without affecting unrelated prod services
- Deployed image:
  - when `live`, the prod gateway reconciled to
    `ghcr.io/mfshaf7/openclaw-gateway@sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Pod:
  - `live`: `deployment/openclaw-gateway` returned with `1/1` ready and
    `service/openclaw-gateway` existed
  - `traffic-stopped`: the gateway deployment and service were removed while
    `platform-versions`, `openclaw-gateway-secrets`, and
    `serviceaccount/platform-vault-reader` remained
  - `quarantined`: the namespace returned to only
    `configmap/kube-root-ca.crt` and `serviceaccount/default`
  - final `suspended`: the namespace remained in the same quiet posture as
    `quarantined`
- Functional verification:
  - `live`:
    - Argo showed `openclaw-gateway`, `platform-secrets-prod`, and
      `platform-version`
    - lifecycle configmap reported `state=live runtimeActive=true
      trafficActive=true promotionAllowed=true prodVerificationStatus=pending`
  - `traffic-stopped`:
    - Argo no longer showed `openclaw-gateway`
    - Argo still showed `platform-secrets-prod` and `platform-version`
    - lifecycle configmap reported `state=traffic-stopped runtimeActive=false
      trafficActive=false promotionAllowed=true prodVerificationStatus=inactive`
  - `quarantined`:
    - Argo no longer showed `openclaw-gateway`, `platform-secrets-prod`, or
      `platform-version`
    - lifecycle configmap reported
      `incidentRef=drill/openclaw-prod-lifecycle-2026-04-17` and
      `promotionAllowed=false`
  - final `suspended`:
    - lifecycle configmap reported `state=suspended`
    - `incidentRef` was cleared
    - `promotionAllowed=true`
- Residual risk:
  - the lifecycle policy and cluster behavior are now aligned, but promotion
    blocking while `quarantined` was evidenced through lifecycle contract state
    and validation rather than a full attempted `stage -> prod` promotion,
    because no current approved stage candidate was prepared for that purpose

## Follow-Up

- Required follow-up: None for the drill itself; prod intentionally remains
  suspended while stage continues as the active stabilization environment
- Optional hardening:
  - add a dedicated operator-facing summary command or runbook section that
    makes the retained-surfaces expectation for `traffic-stopped` easier to
    inspect in one step
- Owner: platform engineering
