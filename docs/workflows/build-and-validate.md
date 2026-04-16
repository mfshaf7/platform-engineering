# Build And Validate

## Purpose

This workflow validates the shared repository on every pull request and on
pushes to `main`.

It is the baseline guardrail for structure, governance docs, Helm charts,
Terraform, and OpenClaw environment contracts.

## Trigger

- automatic on `pull_request`
- automatic on pushes to `main`

## Inputs Or Parameters

- none

## Permissions And Approval Surface

- normal repository read permissions
- no environment gate
- reviewers should treat a failing run as a merge blocker

## Outputs And Side Effects

- PR or commit status checks
- rendered manifests in CI temp space only
- published prod version metadata display on `main`

It does not mutate Git state or live runtime.

## Operator Evidence

Capture:

- workflow run URL
- status of the `validate` job
- failing step name if the run is red

## Related Docs

- [../standards/ci-cd.md](../standards/ci-cd.md)
- [../standards/review-and-approval-model.md](../standards/review-and-approval-model.md)
