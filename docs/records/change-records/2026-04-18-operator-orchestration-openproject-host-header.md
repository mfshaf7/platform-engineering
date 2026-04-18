# 2026-04-18 operator-orchestration-service OpenProject host header fix

## Summary

The first live broker pod started successfully but stayed unready because
OpenProject rejected its readiness-time API call with `400 Bad Request` until
the request used the runtime's canonical host header.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- OpenProject runtime contract owner: `platform-engineering`
- broker non-secret runtime env owner: `platform-engineering`

## Root Cause

The shared broker deployment set the in-cluster OpenProject base URL but did not
set `OPENPROJECT_HOST_HEADER`. The current OpenProject runtime is configured
with `OPENPROJECT_HOST__NAME=127.0.0.1:32083`, so API calls routed through the
cluster service need the matching `Host` header to avoid `400 Bad Request`.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`
- `products/openproject/idea-backlog-contract.md`

## Artifact And Deployment Evidence

- failing broker readiness behavior:
  - `GET /readyz` returned `503`
- live proof of runtime requirement:
  - `GET /api/v3/projects/workspace-proposals` against
    `http://openproject.openproject.svc.cluster.local:8080` returned `400`
    without the host header
  - the same request returned `200` with:
    - `Host: 127.0.0.1:32083`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - broker pod readiness
  - broker `/readyz` and `/version`
  - stage `/idea` capture rehearsal

## Follow-Up

- merge the host-header runtime fix
- refresh `platform-root-shared`
- verify broker readiness and continue the stage capture lane
