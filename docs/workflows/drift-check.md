# Drift Check

## Purpose

This workflow checks for obvious source-side platform drift in prod and stage
overlay paths.

It is a lightweight repository contract check, not a live-cluster reconciliation
audit.

## Trigger

- scheduled every six hours
- manual `workflow_dispatch`

## Inputs Or Parameters

- none

## Permissions And Approval Surface

- repository read only
- no environment gate

## Outputs And Side Effects

- scheduled or manual check result
- no Git mutation
- no live deployment change

## Operator Evidence

Capture:

- workflow run URL
- failing file or overlay path when the check is red

## Related Docs

- [../standards/gitops.md](../standards/gitops.md)
- [../architecture/current-platform-topology.md](../architecture/current-platform-topology.md)
