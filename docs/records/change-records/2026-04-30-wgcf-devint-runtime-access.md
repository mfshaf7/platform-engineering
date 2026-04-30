---
security_evidence:
  review_areas:
    - runtime
    - delivery
  findings: []
  risks: []
  workstreams:
    - workspace-governance-control-fabric
---

# WGCF Dev-Integration Runtime Access

## Summary

- Date: 2026-04-30
- Short title: WGCF dev-integration runtime access
- Environment: dev-integration
- Severity: normal platform enablement

## Classification

- Type: shared component dev-integration admission
- User-facing impact: operators and future Governance Operations Console work
  can consume WGCF through a real local-k3s API Service instead of a source-only
  scaffold.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos:
  - `workspace-governance-control-fabric`
  - `workspace-governance`
  - `security-architecture`
- Related ADR: None

## Runtime Decision

Platform accepts the `governance-control-fabric` dev-integration profile as a
local-k3s runtime lane.

The accepted day-one runtime is intentionally small:

- one WGCF API Deployment
- one ClusterIP Service
- one local PostgreSQL StatefulSet, Service, and PVC for fabric-local metadata
- one migration Job that runs `alembic upgrade head` before API readiness
- image source: `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-<source-sha>`
- shared runner commands: `devint-up`, `devint-status`, `devint-smoke`,
  `devint-access`, `devint-down`, `devint-reset`, and `devint-promote-check`
- no governed stage/prod deployment approval
- no worker runtime activation yet

## Source Changes

- Repo: `workspace-governance-control-fabric`
- Commit(s):
  - `7c0c09d78df37a995a4e413aaeb25a5b857fc2c2` from PR #18,
    `Add WGCF dev-integration runtime`
  - `296a4deca882e52eb1d804df9976ec01866c4698` from PR #19,
    `Fail closed on WGCF devint status errors`
- Guardrail added:
  - Dockerfile and image build workflow
  - local-k3s dev-integration profile scripts
  - fail-closed Kubernetes status behavior for connection errors
  - profile manifest rendering tests

## Artifact And Deployment Evidence

- Build workflow run: `Build WGCF Image`
  `github://mfshaf7/workspace-governance-control-fabric/actions/runs/25177498034`
- Published image tag:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-296a4de`
- Published digest:
  `sha256:b37fa7cbebbc289486e9199ff09534d943c003b936b8257ee8050440590dc8c1`
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: run
  `make devint-up PROFILE=governance-control-fabric`
- Why it was environment drift instead of source defect: None; this is new
  platform enablement, not recovery.
- Recovery command or procedure:
  `make devint-down PROFILE=governance-control-fabric` scales the local API
  Deployment to zero while preserving profile state; `make devint-reset
  PROFILE=governance-control-fabric` deletes the local namespace and state.

## Live Verification

- App health: `make devint-smoke PROFILE=governance-control-fabric` passed.
- Deployed image:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-296a4de`
- Namespace: `devint-governance-control-fabric-mfshaf7`
- Pod evidence:
  - API pod `workspace-governance-control-fabric-api-f8556d769-9tmxx` was
    `1/1 Running`.
  - PostgreSQL pod `workspace-governance-control-fabric-postgresql-0` was
    `1/1 Running`.
  - Migration Job `workspace-governance-control-fabric-api-migrate` was
    `Complete 1/1`.
- Persistent storage evidence:
  `data-workspace-governance-control-fabric-postgresql-0` was `Bound` with
  `2Gi` `local-path` storage.
- Functional verification:
  - `GET /healthz` returned `status=ok`.
  - `GET /readyz` returned `ready=true`.
  - `GET /v1/status` returned a redacted
    `WGCF_DATABASE_URL` sourced from environment configuration.
  - `GET /v1/graph/query?scope=repo:workspace-governance-control-fabric`
    succeeded through the k3s Service.
  - `POST /v1/validation-plans` produced a smoke validation plan.
  - `GET /v1/receipts` returned receipt metadata without raw artifact output.
  - Database migration artifact recorded Alembic `PostgresqlImpl` execution.
- Residual risk: dev-integration remains local evidence only and must not be
  represented as governed stage/prod readiness.

## Follow-Up

- Required follow-up: stage/prod deployment design remains separate and gated.
- Optional hardening: add governed stage/prod PostgreSQL, image pinning, and
  worker activation only after the next security/platform gate.
- Owner: `platform-engineering`
