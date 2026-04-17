# Manage Prod Environment

## Purpose

This workflow changes the desired prod OpenClaw lifecycle state by creating a
Git branch that sets the bounded prod lifecycle contract.

It owns the source-side prod lifecycle intent, not direct runtime mutation.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- `state`
  - `live` or `suspended`
- `reason`
  - short reason for the lifecycle change
- `incident_ref`
  - optional incident or ticket reference
- `operation_note`
  - optional operator note

## Permissions And Approval Surface

- repository write
- pull-request write
- `prod` environment gate

This workflow is the governed red-button path for OpenClaw prod runtime
suspension.

## Outputs And Side Effects

- lifecycle branch when desired state changed
- compare URL in the workflow summary
- updated prod lifecycle, prod Argo kustomization, lifecycle configmap, and
  prod verification files

The workflow does not bypass Git review. It creates the change that must still
be reviewed and merged.

## Operator Evidence

Capture:

- workflow run URL
- requested prod lifecycle state
- reason and incident reference
- prod verification status line
- lifecycle branch or merged PR URL

## Related Docs

- [../../products/openclaw/runbooks/manage-prod-lifecycle.md](../../products/openclaw/runbooks/manage-prod-lifecycle.md)
- [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
