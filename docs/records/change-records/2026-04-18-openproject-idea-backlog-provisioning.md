# OpenProject Idea Backlog Provisioning

## Summary

- Date: 2026-04-18
- Short title: provisioned canonical OpenProject idea backlog and removed demo baseline
- Environment: prod platform-integrated OpenProject runtime
- Severity: medium

## Classification

- Type:
  - product runtime configuration
- User-facing impact:
  - removed the upstream demo projects from the live OpenProject UI
  - added the canonical `workspace-proposals` backlog model for future operator
    idea capture and triage

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
  - OpenProject still exposed upstream seed/demo projects and had no canonical
    backlog project for operator proposals
- Actual root cause:
  - the product had been integrated as a runtime and access surface, but the
    application-level backlog model had never been provisioned
- Why it escaped earlier controls:
  - existing controls covered deployment and access, not app-internal OpenProject
    project model convergence

## Source Changes

- Repo:
  - platform-engineering
- Commit(s):
  - pending merge at review time
- Guardrail added:
  - product-scoped provisioning script
  - runbook
  - make target
  - live change record

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
  - unchanged; this change was applied inside the OpenProject runtime database,
    not through an Argo-managed manifest revision

## Host Or Runtime Recovery

- Required host/runtime action:
  - executed `make openproject-configure-idea-backlog`
- Why it was environment drift instead of source defect:
  - the canonical backlog model existed only as a documented target contract
    until it was provisioned inside the live OpenProject runtime
- Recovery command or procedure:
  - `make openproject-configure-idea-backlog`

## Live Verification

- App health:
  - `openproject-web` rollout completed and the pod returned to `Ready`
- Deployed image:
  - `docker.io/openproject/openproject:17.2.3-slim`
- Pod:
  - `openproject-web-686fbbd58d-tfdx5`
- Functional verification:
  - demo projects deleted:
    - `demo-project`
    - `your-scrum-project`
  - canonical project present:
    - `workspace-proposals`
  - proposal types present:
    - `Idea`
    - `Governance Proposal`
    - `Security Proposal`
    - `Product Proposal`
    - `Component Proposal`
  - proposal statuses present:
    - `captured`
    - `triaged`
    - `parked`
    - `owner-assigned`
    - `accepted`
    - `rejected`
    - `implemented`
    - `superseded`
  - required custom fields present:
    - `Source Surface`
    - `Source Reference`
    - `Suspected Owner`
    - `Affected Scope`
    - `Trust Boundary Areas`
    - `Promotion Target`
    - `Triage Decision ID`
    - `Triage Confidence`
    - `AI Assist Lane`
    - `Revisit On`
  - workflow convergence:
    - each proposal type has `704` workflow rows
    - derived from `11` distinct semantic roles and the `8 x 8` proposal-status
      transition matrix
- Residual risk:
  - the dedicated automation user and Vault-backed API token are still deferred
  - field-id mapping is still implicit and should be recorded before the broker
    writes to OpenProject

## Follow-Up

- Required follow-up:
  - create the `operator-orchestration-service` automation user and single-purpose
    API token for `workspace-proposals`
  - record the final field-id mapping used by the broker adapter
- Optional hardening:
  - add a verification mode to the provisioning script that prints the live
    project, type, status, field, and workflow summary without mutating state
- Owner:
  - platform-engineering
