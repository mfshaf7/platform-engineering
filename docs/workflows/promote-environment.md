# Promote Environment

## Purpose

This workflow creates the prod promotion branch from an approved stage
candidate.

It carries the governed `stage -> prod` digest promotion path for OpenClaw.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- `source_environment`
  - currently `stage`
- `target_environment`
  - currently `prod`
- `promotion_note`
  - optional note
- `suspend_stage_environment`
  - whether stage should be suspended after promotion intent is created

## Permissions And Approval Surface

- repository write
- pull-request write
- `prod` environment gate

Promotion is allowed only from an approved stage candidate.

## Outputs And Side Effects

- promotion branch for the prod contract update
- compare URL in the workflow summary
- updated prod versions and related stage readiness/lifecycle files

The workflow does not bypass Git review. It creates the change that must still
be reviewed and merged.

## Operator Evidence

Capture:

- workflow run URL
- promoted image digest
- promoted source SHAs
- approved stage verification reference
- promotion branch or merged PR URL

## Related Docs

- [../../products/openclaw/runbooks/promote-stage-to-prod.md](../../products/openclaw/runbooks/promote-stage-to-prod.md)
- [../standards/governed-change-model.md](../standards/governed-change-model.md)
