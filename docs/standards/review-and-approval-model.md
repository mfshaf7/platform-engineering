# Review And Approval Model

## Purpose

This standard defines how review and approval should work for shared platform
changes.

The goal is to make ownership, review routing, and approval expectations
explicit instead of implicit.

## Repo-Enforced Controls

The repository now enforces these minimum controls:

- [../../.github/CODEOWNERS](../../.github/CODEOWNERS)
- [../../.github/pull_request_template.md](../../.github/pull_request_template.md)
- [../../.github/workflows/build-and-validate.yaml](../../.github/workflows/build-and-validate.yaml)
- [../../.github/workflows/security-posture.yaml](../../.github/workflows/security-posture.yaml)

These controls route ownership, force a governance declaration, and block
obvious structural drift.

## Required Reviewer Routes

Use these reviewer routes for meaningful changes:

| Change type | Primary reviewer route | Additional reviewer route |
| --- | --- | --- |
| shared docs, workflows, or control-plane changes | platform owner via `CODEOWNERS` | security or architecture review when trust boundary changed |
| product-local integration change under `products/<product>/` | owning product path via `CODEOWNERS` | platform owner when shared platform surfaces changed |
| identity, secrets, delivery, runtime, or AI-governance change | platform owner | `security-architecture` review input |
| governed rollout or promotion change | platform owner | release authority review |
| host-drift or break-glass recovery change | platform owner | security or architecture review when privilege or audit posture changed |

## Security Review Route

When the change affects identity, secrets, GitOps delivery, privileged runtime,
or AI-governed action paths, review against the checklist in the
`security-architecture` repo:

- `security-architecture/docs/reviews/security-review-checklist.md`

Do not treat the PR template alone as a substitute for that review.

## Approval Matrix

| Change class | Merge expectation | Deployment expectation |
| --- | --- | --- |
| documentation-only structure change | reviewed PR with valid governance declaration | no rollout required |
| shared design change | reviewed PR plus ADR | rollout only after the owning path is ready |
| governed runtime-affecting source or platform change | reviewed PR plus change record when applied live | use the normal artifact and Argo path |
| prod promotion | approved stage candidate, reviewed promotion PR, and prod environment gate | reconcile through Argo after merge |
| host/runtime drift repair | reviewed PR or follow-up record plus updated runbook/provisioning path | host owner executes documented repair path |

## GitHub Environment Gates

Workflow-level environment gates should be used for actions that can change
governed environment state.

Current intended gates:

- `stage`
  - stage lifecycle and stage readiness workflows
- `prod`
  - prod promotion workflow

Environment reviewer configuration itself lives in GitHub settings, not in this
repository, so operators must keep those settings aligned with this standard.

## Branch Protection Expectations

Branch protection is an external GitHub setting, but the intended policy is:

- protect `main`
- require PR merge instead of direct push for meaningful changes
- require status checks from build and governance validation
- require code-owner review when GitHub settings support it

This repository documents the model; GitHub settings must enforce it.

## Evidence Before Approval

Before merging a meaningful change, reviewers should be able to answer:

- who owns the change
- whether an ADR is required
- whether a change record is required
- which docs changed
- which validations ran
- whether security review was required and how it was satisfied

## Anti-Patterns

These are review failures:

- approving a high-risk change with no governance declaration
- merging a trust-boundary change without a reviewer considering the security
  checklist
- treating `CODEOWNERS` as enough when a real approval decision is still needed
- merging a workflow change without updating the workflow catalog
