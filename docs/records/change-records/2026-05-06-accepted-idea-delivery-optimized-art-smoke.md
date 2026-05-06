# 2026-05-06 Accepted-Idea Delivery Optimized ART Smoke

## Summary

- Date: 2026-05-06
- Short title: Accepted-idea-delivery optimized ART smoke coverage
- Environment: dev-integration
- Severity: control hardening

## Classification

- Type: runtime smoke and operator-runbook alignment
- User-facing impact: operators can use `make devint-smoke
  PROFILE=accepted-idea-delivery` to prove the optimized ART packet reads and
  first landing-unit closeout evidence without mutating the persistent ART lane

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`
- Related ADR: `docs/decisions/adr/ADR-013-openproject-proposal-to-delivery-split-and-one-art-model.md`

## Root Cause

- Immediate failure: the platform operator runbook did not state that the
  accepted-idea-delivery smoke now covers optimized ART packet and closeout
  evidence surfaces.
- Actual root cause: the OOS profile smoke was expanded for #650, but the
  platform-owned profile operation surface also needed to describe the new
  read-only smoke scope.
- Why it escaped earlier controls: previous smoke guidance listed the older
  delivery draft and project verification checks only.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): pending PR
- Guardrail added:
  - runbook

## Artifact And Deployment Evidence

- Build workflow run: None.
- Published image tag: None.
- Published digest: None.
- Recorded prod revision: None.
- Argo application revision: None.

## Host Or Runtime Recovery

None.

## Live Verification

- App health: `DEVINT_OPENPROJECT_LOCAL_PORT=28183
  DEVINT_OPENPROJECT_HOST_HEADER=localhost:18183 DEVINT_BROKER_LOCAL_PORT=28180
  make devint-smoke PROFILE=accepted-idea-delivery` passed from
  `platform-engineering`.
- Deployed image: None; profile uses local source mount.
- Pod: `devint-accepted-idea-delivery-mfshaf7/operator-orchestration-service`
  rolled out during smoke.
- Functional verification: smoke output included `optimized ART packet reads`
  with `active_open_descendants=5` and `landing-unit closeout evidence read`
  with `work-item-660` status `done` and valid completion evidence.
- Residual risk: the first dogfood closeout proof is tied to current #650
  dev-integration data; a future reset may need a newer closed landing-unit
  proof id.

## Follow-Up

- Required follow-up: complete ART #668 after OOS PR #111 and this platform
  runbook PR are merged.
- Optional hardening: promote a generic closed-landing-unit fixture or broker
  selector if this smoke must survive a destructive devint reset without #650
  data.
- Owner: `platform-engineering`
