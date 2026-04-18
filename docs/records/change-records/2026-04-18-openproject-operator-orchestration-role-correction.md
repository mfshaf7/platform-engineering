---
security_evidence:
  review_areas:
    - identity
    - runtime
  findings: []
  risks: []
  workstreams:
    - WS-003
---

# OpenProject Operator-Orchestration Role Correction

## Summary

- Date: 2026-04-18
- Short title: corrected broker OpenProject roles so capture can create work packages
- Environment: prod platform-integrated OpenProject runtime
- Severity: medium

## Classification

- Type:
  - product runtime configuration
  - machine identity least-privilege correction
- User-facing impact:
  - no direct operator UX change
  - broker-backed idea capture can now create work packages in the canonical
    backlog

## Ownership

- Owning repo or layer: platform-engineering
- Related repos:
  - operator-orchestration-service
  - security-architecture
- Related ADR:
  - None

## Root Cause

- Immediate failure:
  - the broker service identity could read `workspace-proposals` but API-backed
    work package creation returned `MissingPermission`
- Actual root cause:
  - the provisioned role set (`Reader` plus `Work package editor`) omitted the
    `add_work_packages` permission needed for capture
- Why it escaped earlier controls:
  - earlier validation checked identity existence, project membership, Vault
    token custody, and read access, but did not perform a live create probe

## Source Changes

- Repo:
  - platform-engineering
- Commit(s):
  - pending merge at review time
- Guardrail added:
  - identity converger now ensures a dedicated `Work package creator`
    `ProjectRole`
  - runbook and contract updated to the corrected least-privilege role set
  - live change record for the permission correction

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
  - unchanged; the correction was applied inside the OpenProject runtime
    database and existing Vault path, not through an Argo manifest update

## Host Or Runtime Recovery

- Required host/runtime action:
  - `env VAULT_TOKEN=... make openproject-provision-operator-orchestration-identity`
- Why it was environment drift instead of source defect:
  - the source contract said the identity was correct, but the live OpenProject
    permission model proved the role set was under-permissioned for capture
- Recovery command or procedure:
  - `env VAULT_TOKEN=... make openproject-provision-operator-orchestration-identity`

## Live Verification

- App health:
  - OpenProject web deployment remained healthy during role correction
- Deployed image:
  - `docker.io/openproject/openproject:17.2.3-slim`
- Pod:
  - `openproject-web-686fbbd58d-tfdx5`
- Functional verification:
  - identity now converges to:
    - `Reader`
    - `Work package creator`
    - `Work package editor`
  - OpenProject API create probe succeeded:
    - `POST /api/v3/projects/workspace-proposals/work_packages`
    - created work package id `37`
    - type `Idea`
    - status `captured`
  - cleanup completed:
    - temporary probe work package `37` deleted immediately after verification
- Residual risk:
  - broker runtime admission, Vault Kubernetes auth, and secret delivery remain
    deferred

## Follow-Up

- Required follow-up:
  - add a repo-owned validation path that exercises the live create permission
    during future broker identity changes
- Optional hardening:
  - add a non-mutating verify mode that confirms the corrected role set before
    attempting rotation or reprovisioning
- Owner:
  - platform-engineering
