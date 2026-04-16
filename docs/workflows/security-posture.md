# Security Posture

## Purpose

This workflow validates minimum repository security posture and governance
surfaces.

It is a repo-structure and policy check, not a substitute for human security
review.

## Trigger

- automatic on `pull_request`
- manual `workflow_dispatch`

## Inputs Or Parameters

- none

## Permissions And Approval Surface

- repository read only
- no environment gate

## Outputs And Side Effects

- status check for minimum security/governance files
- no Git mutation
- no live runtime change

## Operator Evidence

Capture:

- workflow run URL
- failing posture check if the run is red

## Related Docs

- [../standards/review-and-approval-model.md](../standards/review-and-approval-model.md)
- [../standards/secrets.md](../standards/secrets.md)
