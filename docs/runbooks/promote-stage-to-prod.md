# Promote Stage To Prod

## Purpose

This runbook defines the intended promotion path between the two declared
environments.

## Expected Flow

1. update and validate `stage`
2. build and publish the stage gateway artifact from pinned SHAs
2. allow Argo CD to reconcile `stage`
3. verify stage workload, observability, and host integration expectations
4. copy the approved version pins into `prod`
5. merge the production promotion change
6. verify `prod` after reconciliation

## Current Operator Inputs

- [environments/stage/versions.yaml](../../environments/stage/versions.yaml)
- [environments/prod/versions.yaml](../../environments/prod/versions.yaml)
- [.github/workflows/promote-environment.yaml](../../.github/workflows/promote-environment.yaml)
