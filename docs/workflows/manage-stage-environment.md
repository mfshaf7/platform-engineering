# Manage Stage Environment

## Purpose

This workflow changes the desired stage lifecycle state by creating a Git
branch that resumes or suspends stage components.

It owns the source-side stage lifecycle intent, not direct runtime mutation.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- `action`
  - `resume` or `suspend`
- `components`
  - comma-separated component set
- `operation_note`
  - optional operator note

## Permissions And Approval Surface

- repository write
- pull-request write
- `stage` environment gate

Stage should stay suspended unless there is active rehearsal or validation
work.

## Outputs And Side Effects

- lifecycle branch when desired state changed
- compare URL in the workflow summary
- updated stage kustomization, verification, and promotion-readiness files

## Operator Evidence

Capture:

- workflow run URL
- requested action and component set
- readiness status line
- lifecycle branch or merged PR URL

## Related Docs

- [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
- [../../products/openclaw/runbooks/promote-stage-to-prod.md](../../products/openclaw/runbooks/promote-stage-to-prod.md)
