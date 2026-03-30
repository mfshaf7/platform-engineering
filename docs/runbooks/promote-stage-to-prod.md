# Promote Stage To Prod

## Purpose

This runbook defines the intended promotion path between the two declared
environments.

## Expected Flow

1. update and validate `stage`
2. build and publish the stage gateway artifact from pinned SHAs
3. allow Argo CD to reconcile `stage`
4. verify stage workload, observability, and host integration expectations
5. copy the approved version pins into `prod`
6. merge the production promotion change
7. verify `prod` after reconciliation

## Current Stage Reality

- `stage` currently runs the local `openclaw:local` gateway image on the
  `Platform-Core` node.
- promotion to `prod` should happen only after the governed gateway image has
  been built from pinned SHAs and published to GHCR.
- `prod` placeholders should remain untouched until there is an approved image
  tag and digest to record.

## Immutable Promotion Rule

- record the produced GHCR digest in the target environment values before
  rollout
- prefer `repository@sha256:...` over mutable tag-only deployment references
- keep the image tag for operator readability, but treat the digest as the
  deployment truth

## Current Operator Inputs

- [environments/stage/versions.yaml](../../environments/stage/versions.yaml)
- [environments/prod/versions.yaml](../../environments/prod/versions.yaml)
- [.github/workflows/promote-environment.yaml](../../.github/workflows/promote-environment.yaml)
