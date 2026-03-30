# Promote Stage To Prod

## Purpose

This runbook defines the intended promotion path between the two declared
environments.

## Expected Flow

1. update and validate `stage`
2. build and publish the stage gateway artifact from pinned SHAs
3. allow Argo CD to reconcile `stage`
4. verify stage workload, observability, and host integration expectations
5. run `.github/workflows/promote-environment.yaml`
6. approve the protected `prod` promotion job and review the generated PR
7. merge the production promotion change
8. verify `prod` after reconciliation

## Current Promotion Contract

- `stage` now runs a governed GHCR-backed gateway image pinned by digest.
- promotion to `prod` is allowed only from `stage` to `prod`.
- the promotion workflow copies the approved digest and source SHAs into the
  `prod` contract and opens a PR instead of mutating `main` directly.
- the workflow should be bound to a protected GitHub environment named `prod`
  so required reviewers gate the job before the PR is created.

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
- [scripts/promote_environment.py](../../scripts/promote_environment.py)
- [scripts/validate_environment_contract.py](../../scripts/validate_environment_contract.py)
