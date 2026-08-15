# OpenProject Proposal Workflow-State Provisioning

## Summary

- Date: 2026-08-16
- Short title: Provision bounded Proposal workflow-state storage
- Environment: local `dev-integration` OpenProject
- Severity: planned governed change

## Classification

- Type: deployment/artifact change
- User-facing impact: Workspace Proposal records can carry versioned route,
  source-custody, command, receipt, and prepared-handoff state without placing
  event history in the custom field.

## Ownership

- Owning repo or layer: `platform-engineering` OpenProject integration
- Related repos: `operator-orchestration-service`,
  `governance-operations-console`
- Related ADR: None; the approved ART #417 architecture packet is the design
  authority for this bounded integration slice.

## Root Cause

- Immediate failure: None; this was planned provisioning under ART #857.
- Actual root cause: The canonical Proposal record had no bounded,
  machine-validated storage location for live workflow state.
- Why it escaped earlier controls: The Proposal surface previously operated on
  local fixtures and did not have a live mutation adapter.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): PR #212
- Guardrail added:
  - JSON Schema validation for persisted Proposal workflow state
  - fail-closed field and schema checks in the OpenProject admin validator
  - regression coverage for schema versioning and resolved repository custody
  - operator and consumer boundary documentation

## Artifact And Deployment Evidence

- Build workflow run: GitHub PR #212 `validate` and `repo-posture`
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: Ran
  `make openproject-configure-idea-backlog` against the local
  `dev-integration` OpenProject runtime.
- Why it was environment drift instead of source defect: Not applicable; this
  was an intentional schema rollout.
- Recovery command or procedure: Re-run the idempotent provisioning command;
  it must not populate existing Proposal records.

## Live Verification

- App health: OpenProject remained available after provisioning.
- Deployed image: Existing local OpenProject image; no image change.
- Pod: local OpenProject web pod.
- Functional verification: Custom field `Proposal Workflow State` was created
  as field id `52`, scoped to Workspace Proposals and its five Proposal types,
  non-searchable, non-filterable, optional, and bounded to 32,768 characters.
  Existing Proposal count and record digest remained unchanged; valid state
  round-tripped in a rolled-back transaction and oversized state was rejected.
- Residual risk: OOS command and projection APIs are delivered separately under
  ART #858. Until then, the field is provisioned but has no supported live
  operator mutation path.

## Follow-Up

- Required follow-up: Complete ART #858 and retain OOS as the only admitted
  workflow-state mutation adapter.
- Optional hardening: Add governed stage rehearsal when the Proposal workflow
  reaches that maturity.
- Owner: Workspace Delivery ART #417.
