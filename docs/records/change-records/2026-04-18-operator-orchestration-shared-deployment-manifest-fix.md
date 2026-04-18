# 2026-04-18 operator-orchestration-service shared deployment manifest fix

## Summary

The first post-admission reconciliation of `operator-orchestration-service`
reached Argo manifest generation and then failed because the shared deployment
manifest had invalid YAML indentation under the container image field.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- shared runtime manifest owner: `platform-engineering`

## Root Cause

The new shared deployment manifest was committed with the container `image`
field aligned to the container list item instead of the container object body.
That left the GitOps source syntactically invalid even though the surrounding
contract and digest pin were correct.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- failing repo-server build evidence:
  - ``kustomize build .../environments/shared/operator-orchestration-service`` failed with:
    `MalformedYAMLError: yaml: line 15: did not find expected '-' indicator in File: deployment.yaml`
- affected child application:
  - `argocd/operator-orchestration-service`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - successful `operator-orchestration-service` manifest generation
  - namespace, pod, and endpoint readiness in `operator-orchestration-service`

## Follow-Up

- merge the shared deployment manifest fix
- refresh `platform-root-shared`
- verify runtime readiness and continue the stage `/idea` capture rehearsal
