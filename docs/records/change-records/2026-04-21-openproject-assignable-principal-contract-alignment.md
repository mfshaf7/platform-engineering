---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
    - runtime
  findings: []
  risks: []
  workstreams:
    - WS-021
---

# OpenProject Assignable Principal Contract Alignment

## Summary

- Date: 2026-04-21
- Short title: OpenProject assignable-principal contract alignment
- Environment: devint-accepted-idea-delivery
- Severity: medium

## Classification

- Type:
  - app/plugin source bug
- User-facing impact:
  - operator runbooks and helper text no longer imply arbitrary `admin`
    assignment on broker-backed create or update paths

## Ownership

- Owning repo or layer: `platform-engineering` product-owned OpenProject
  operator surface
- Related repos:
  - `operator-orchestration-service`
  - `security-architecture`
- Related ADR:
  - None

## Root Cause

- Immediate failure:
  - the broker create surface was proven live only after the correct structure
    role was restored, but the platform operator docs still implied arbitrary
    assignee selection such as `ASSIGNEE_LOGIN=admin`
- Actual root cause:
  - the operator instruction layer had drifted from the backend's
    assignable-principal model
- Why it escaped earlier controls:
  - the previous proof focused on workflow reachability more than contract
    precision for assignable-principal behavior

## Source Changes

- Repo: `platform-engineering`
- Commit(s): None yet at record time
- Guardrail added:
  - runbook
  - contract

## Artifact And Deployment Evidence

- Build workflow run: None
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action:
  - None
- Why it was environment drift instead of source defect:
  - Not applicable; this slice corrected the operator contract and helper text
- Recovery command or procedure:
  - None

## Live Verification

- App health:
  - devint OpenProject and broker remained healthy during the contract update
- Deployed image:
  - None
- Pod:
  - `devint-accepted-idea-delivery-openproject-web`
- Functional verification:
  - live broker create proof succeeded after role reconciliation
  - platform governance and operational doc validators passed
- Residual risk:
  - assignable-principal behavior still depends on real project membership, by
    design

## Follow-Up

- Required follow-up:
  - None
- Optional hardening:
  - add a dedicated operator surface later if bulk assignee validation becomes
    common
- Owner:
  - `platform-engineering`
