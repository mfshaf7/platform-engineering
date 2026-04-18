# 2026-04-18 operator-orchestration-service namespace admission

## Summary

The first live reconciliation of `operator-orchestration-service` failed because
the `platform-core` AppProject did not allow the new
`operator-orchestration-service` namespace. Argo created the child Application
object but rejected its spec before any runtime resources could be applied.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `security-architecture`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- AppProject destination allowlist owner: `platform-engineering`
- shared runtime admission review owner: `security-architecture`

## Root Cause

The shared runtime admission work added a new child Application and namespace
but did not extend the parent `platform-core` AppProject destination allowlist.
That left the GitOps definition internally inconsistent until the first live
refresh exposed the mismatch.

## Source Changes

- `environments/shared/argocd/platform-core-project.yaml`

## Artifact And Deployment Evidence

- failing Argo child app condition:
  - `application destination server 'https://kubernetes.default.svc' and namespace 'operator-orchestration-service' do not match any of the allowed destinations in project 'platform-core'`
- affected child application:
  - `argocd/operator-orchestration-service`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - `argocd/operator-orchestration-service` sync and health
  - namespace and pod readiness in `operator-orchestration-service`

## Follow-Up

- merge the AppProject namespace admission fix
- refresh `platform-root-shared`
- verify the broker runtime and the stage `/idea` path end to end
