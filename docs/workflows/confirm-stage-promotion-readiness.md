# Confirm Stage Promotion Readiness

## Purpose

This workflow records structured stage verification evidence and approval of the
current stage candidate for later prod promotion.

It does not promote anything by itself. It writes the approval state that prod
promotion requires.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- `verification_evidence_ref`
  - required evidence reference for the stage rehearsal
- `verification_results`
  - required check results in `check-id=status` form
- `verification_note`
  - optional operator note stored with the verification update
- `approval_note`
  - optional reviewer note stored with the readiness update

## Permissions And Approval Surface

- repository write
- pull-request write
- `stage` environment gate

Use this only after stage behavior has been tested against the current
candidate.

## Outputs And Side Effects

- readiness branch when approval changed Git state
- compare URL in the workflow summary
- updated `environments/stage/verification.yaml`
- updated `environments/stage/promotion-readiness.yaml`

## Operator Evidence

Capture:

- workflow run URL
- verification evidence reference and recorded check results
- readiness status line from the summary
- readiness branch or merged PR URL when a change was created

## Related Docs

- [../../products/openclaw/runbooks/promote-stage-to-prod.md](../../products/openclaw/runbooks/promote-stage-to-prod.md)
- [../standards/review-and-approval-model.md](../standards/review-and-approval-model.md)
