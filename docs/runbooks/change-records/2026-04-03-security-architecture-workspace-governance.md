# Change Record

## Summary

- Date: 2026-04-03
- Short title: Security-architecture workspace made reproducible
- Environment: prod
- Severity: medium

## Classification

- Type: deployment/artifact bug
- User-facing impact: the `security-architecture` Telegram topic routed correctly but answered from generic bootstrap context instead of the intended specialized workspace.

## Ownership

- Owning repo or layer: `openclaw-isolated-deployment`
- Related repos: `platform-engineering`

## Root Cause

- Immediate failure: the topic session showed `skillFilter=['security-architecture']` but `resolvedSkills=[]`.
- Actual root cause: `/home/node/.openclaw/workspace-security-architecture/...` existed only as live runtime state and was not tracked or materialized from source.
- Why it escaped earlier controls: no deployment-owned workspace template existed and no source-bundle validator checked for it.

## Source Changes

- Repo: `openclaw-isolated-deployment`
- Commit(s): `82231db8b8b6e93befa832b381f8cf278c2b57d0`
- Related repo: `platform-engineering`
- Related commit(s): `89e41902db86152930946bc0f8c3646e443008b2`, `c784f940fe95d04f31da44857fa1307f6714a4e6`, `318f7e069ea7d20d62f7c3675ef6fe5568bb57f5`
- Guardrail added:
  - tracked deployment workspace template
  - source-bundle validator for required workspace materialization
  - ADR and ownership documentation

## Artifact And Deployment Evidence

- Build workflow run: GitHub Actions `Build Gateway Image`
- Published image tag: `prod-0fcdee61af1b`
- Published digest: `sha256:2d8fa4375d409d6b3d7a47ef9933724811953a27710cbdfffb76c95cec131ac7`
- Recorded prod revision: `318f7e069ea7d20d62f7c3675ef6fe5568bb57f5`
- Argo application revision: `318f7e069ea7d20d62f7c3675ef6fe5568bb57f5`

## Host Or Runtime Recovery

- Required host/runtime action: stale live topic session for topic `2` was reset so the next message would start fresh
- Why it was environment drift instead of source defect: the source defect was missing deployment materialization; the session reset was only a temporary live cleanup
- Recovery command or procedure: archive stale session file and remove live session entry

## Live Verification

- App health: Argo `Synced Healthy`
- Deployed image: `ghcr.io/mfshaf7/openclaw-gateway@sha256:2d8fa4375d409d6b3d7a47ef9933724811953a27710cbdfffb76c95cec131ac7`
- Pod: `openclaw-gateway-5d4999f754-b8wr5`
- Functional verification: workspace template is present inside the live prod pod at `/home/node/.openclaw/workspace-security-architecture`
- Residual risk: answer quality still depends on model selection and prompting discipline

## Follow-Up

- Required follow-up: keep `security-architecture` answer quality under review
- Optional hardening: add a dedicated functional test for specialized workspace resolution if the upstream runtime seam allows it
- Owner: platform engineering
