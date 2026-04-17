---
security_evidence:
  review_areas:
    - identity
    - secrets
    - ai
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# OpenProject Idea Backlog Contract

## Summary

- Date: 2026-04-18
- Short title: canonical OpenProject idea backlog contract
- Environment: none
- Severity: medium

## Classification

- Type:
  - product integration contract
- User-facing impact:
  - none yet; this defines the canonical OpenProject project and field model
    for future operator idea capture and triage

## Ownership

- Owning repo or layer: platform-engineering
- Related repos:
  - operator-orchestration-service
  - workspace-governance
  - security-architecture
- Related ADR:
  - None

## Root Cause

- Immediate failure:
  - the broker had no canonical OpenProject backlog contract to target
- Actual root cause:
  - OpenProject existed only as a platform-managed runtime and operator access
    path, not yet as a formally modeled canonical backlog for captured ideas
- Why it escaped earlier controls:
  - OpenProject integration work focused on runtime deployment and access rather
    than on workflow-level automation consumers

## Source Changes

- Repo:
  - platform-engineering
- Commit(s):
  - pending merge at review time
- Guardrail added:
  - product contract
  - change record

## Artifact And Deployment Evidence

- Build workflow run:
  - None
- Published image tag:
  - None
- Published digest:
  - None
- Recorded prod revision:
  - None
- Argo application revision:
  - None

## Host Or Runtime Recovery

- Required host/runtime action:
  - None
- Why it was environment drift instead of source defect:
  - not applicable
- Recovery command or procedure:
  - None

## Live Verification

- App health:
  - None
- Deployed image:
  - None
- Pod:
  - None
- Functional verification:
  - `python3 scripts/validate_repo_structure.py --repo-root .`
  - `python3 scripts/validate_governance_docs.py --repo-root .`
- Residual risk:
  - the project, statuses, custom fields, and dedicated automation identity are
    still target state only until they are actually provisioned in OpenProject

## Follow-Up

- Required follow-up:
  - provision the `workspace-proposals` project and its work package types,
    statuses, and custom fields in OpenProject before activating broker writes
- Optional hardening:
  - document the exact field-id mapping after the project is provisioned
- Owner:
  - platform-engineering
