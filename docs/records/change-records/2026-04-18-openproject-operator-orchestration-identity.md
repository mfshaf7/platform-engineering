---
security_evidence:
  review_areas:
    - identity
    - secrets
  findings: []
  risks: []
  workstreams:
    - WS-003
    - WS-005
---

# OpenProject Operator-Orchestration Identity

## Summary

- Date: 2026-04-18
- Short title: provisioned OpenProject service identity for operator-orchestration-service
- Environment: prod platform-integrated OpenProject runtime
- Severity: medium

## Classification

- Type:
  - product runtime configuration
  - machine identity and secret provisioning
- User-facing impact:
  - none for human operators
  - future broker automation now has a dedicated non-human OpenProject identity

## Ownership

- Owning repo or layer: platform-engineering
- Related repos:
  - operator-orchestration-service
  - security-architecture
- Related ADR:
  - None

## Root Cause

- Immediate failure:
  - the canonical backlog existed, but no dedicated machine identity or Vault-backed
    token existed for the future broker write path
- Actual root cause:
  - the OpenProject backlog contract was defined before the machine identity and
    secret custody control had been implemented
- Why it escaped earlier controls:
  - OpenProject integration had been focused on runtime availability and the
    backlog model itself, not on the downstream broker credential

## Source Changes

- Repo:
  - platform-engineering
- Commit(s):
  - pending merge at review time
- Guardrail added:
  - product-scoped provisioner
  - runbook
  - contract correction for broker-owned Vault secret scope
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
  - unchanged; this change was applied inside the OpenProject runtime database
    and Vault, not through an Argo manifest change

## Host Or Runtime Recovery

- Required host/runtime action:
  - `env VAULT_TOKEN=... make openproject-provision-operator-orchestration-identity`
- Why it was environment drift instead of source defect:
  - the intended machine identity and credential custody model existed only as
    contract and review output until it was provisioned into OpenProject and Vault
- Recovery command or procedure:
  - `env VAULT_TOKEN=... make openproject-provision-operator-orchestration-identity`

## Live Verification

- App health:
  - OpenProject web deployment remained healthy during provisioning
- Deployed image:
  - `docker.io/openproject/openproject:17.2.3-slim`
- Pod:
  - `openproject-web-686fbbd58d-tfdx5`
- Functional verification:
  - OpenProject user present:
    - login `operator-orchestration-service`
    - mail `operator-orchestration-service@local.invalid`
    - status `active`
    - admin `false`
  - project membership narrowed to:
    - `Reader`
    - `Work package editor`
  - named API token present:
    - `openproject-workspace-proposals-v1`
    - token id `3`
  - Vault secret present:
    - `kv/components/operator-orchestration-service/prod/openproject`
    - key `apiToken`
  - API verification:
    - token-backed `GET /api/v3/projects/workspace-proposals`
    - HTTP `200`
    - `_type=Project`
    - `identifier=workspace-proposals`
- Residual risk:
  - the broker runtime itself is not admitted or deployed yet
  - Vault Kubernetes auth and secret delivery for the broker remain deferred
    until runtime admission

## Follow-Up

- Required follow-up:
  - add broker runtime secret-delivery policy and Kubernetes auth only when the
    broker runtime is admitted
  - record field-id mapping for the broker adapter before write operations start
- Optional hardening:
  - add a product-scoped status or verify mode that reports the service user,
    project roles, token presence, and Vault path without mutating state
- Owner:
  - platform-engineering
