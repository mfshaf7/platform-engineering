# Enterprise Workflow Model

## Purpose

This standard defines the target enterprise workflow for the platform.

The goal is to make every meaningful change move through a repeatable path with
clear ownership, decision evidence, rollout evidence, and live verification.

## Workflow Stages

Every meaningful change should move through these stages:

1. classify
2. decide
3. implement
4. validate
5. approve
6. deploy or reconcile
7. attest and record
8. follow up

For architecture-shaping changes, discussion and framing happen before these
stages are executed as implementation work.

## Architecture Discussion Trigger

Before implementation begins, discuss and frame the change first when the
request introduces:

- a new product
- a new shared component or control plane
- a new ingress, gateway, service-mesh, or network authority layer
- a new identity, secret-delivery, storage, or observability subsystem
- a new privileged host-control or runtime-control capability
- a feature where multiple plausible long-term architectures exist

That discussion should make these explicit:

- the target role in the platform
- owner repo and control plane
- trust-boundary impact
- expected workflow maturity
- operator surface and visibility model
- rollout and rollback expectations

The purpose is to avoid accidental architecture by implementation.

## Workflow Maturity Rule

Not every product has the same end-to-end delivery maturity yet.

Treat each product or component as being in one of these states:

| Maturity | Meaning |
| --- | --- |
| source-only | canonical source and repo-local validation exist, but no governed platform rollout path exists yet |
| platform-integrated | product docs, access path, and platform-managed runtime exist, but the product does not yet have a full source-to-stage-to-prod workflow |
| fully governed | source, runtime composition, stage rehearsal, approval, promotion, and production evidence all exist |

Agent and operator behavior must match the actual maturity, not the desired
future state.

If a product does not yet have a full end-to-end governed workflow:

- stop at the highest real governed layer that exists
- do not imply that stage or prod promotion exists when it does not
- do not invent fake release evidence for a path that is not implemented
- update the product README and `AGENTS.md` so the current maturity is explicit
- if a live change is still required, treat it as platform or host-owned change
  with a change record and follow-up to create the missing governed path

The correct answer is not always “carry it to prod.” The correct answer is “go
as far as the real control plane exists, and document the missing layer
honestly.”

## Stage Outputs

| Stage | Required output |
| --- | --- |
| Classify | owning layer, shared component or product, and change type are explicit |
| Decide | ADR when shared design, trust boundary, or long-lived control changes |
| Implement | change lands in the owning repo or host owner path |
| Validate | repo-local validation and environment-relevant checks |
| Approve | reviewed Git change in the release authority path |
| Deploy or reconcile | Argo or host owner path applies the approved state |
| Attest and record | immutable artifact or live host evidence plus change record when required |
| Follow up | residual risk, hardening, or cleanup is captured |

## Real Enterprise Roles

| Role | Primary responsibility |
| --- | --- |
| Requester or incident owner | describes the problem and user-facing impact |
| Owning engineer | classifies, patches, validates, and updates docs |
| Security or architecture reviewer | checks trust boundary, identity, secret, delivery, runtime, and AI implications |
| Release authority | approves pins, digests, and governed rollout state in `platform-engineering` |
| Operator | reconciles, verifies live behavior, and captures runtime evidence |

One person may play multiple roles in a small team, but the workflow still
needs each responsibility covered explicitly.

## Change Classes

| Change class | Typical owner | Required governance expectation |
| --- | --- | --- |
| shared design or control-plane change | shared platform or security owner | ADR required, change record if applied live |
| product-local source or config defect | product owner | change record if it materially changed governed stage or prod |
| runtime composition or artifact defect | product/runtime distribution owner | change record required when rebuilt and promoted |
| host or environment drift repair | platform or host owner | change record required; runbook or provisioning path must be updated |
| temporary containment | incident owner plus owning layer | change record required if live state changed; governed follow-up must also be tracked |

## Product Workflow Expectation

Each product directory under `products/<product>/` should state explicitly:

- the current workflow maturity
- whether stage exists for that product
- whether a governed prod promotion path exists
- the highest operator endpoint that is actually implemented today
- what evidence is expected when the product changes

That product-local statement is authoritative for delivery maturity unless a
shared platform standard overrides it.

## ADR Vs Change Record Matrix

| Situation | ADR required | Change record required |
| --- | --- | --- |
| shared platform design changes | Yes | Only if the change was also production-impacting |
| trust-boundary, secret, identity, or rollout-model change | Yes | Yes when applied to a governed environment |
| production incident with only a source or config fix | No, unless design changed | Yes |
| host/runtime drift repair with no design change | No | Yes |
| product-local feature with no shared design impact | No | Only if it materially changed a governed environment |
| temporary incident containment | No | Yes if it affected live governed state; follow-up governed fix must also be recorded |

## Decision Rule

Use an ADR when the answer to any of these is yes:

- does this change a shared control plane
- does this change a trust boundary
- does this change the long-lived ownership model
- will future operators need to preserve this decision intentionally

Use a change record when the answer to any of these is yes:

- did this affect stage or prod behavior
- did this change approved digests, pins, or host-owned live state
- did this require an incident repair or governed rollout
- will another operator need deployment evidence later

If both are true, both are required.

## Required Review Gates

Every meaningful PR should explicitly consider:

- identity impact
- secrets impact
- delivery and GitOps impact
- runtime or host-control impact
- AI or prompt/tooling impact when applicable

If any of those changed and the control is durable, the PR should update the
relevant standard, component doc, ADR, or change record instead of burying the
decision in code review comments.

## PR Governance Contract

Every meaningful PR should declare:

- change classification
- affected shared component or product
- whether an ADR is required, and the link or `N/A`
- whether a change record is required, and the link or `N/A`
- which docs were updated
- which validation was run

Use:

- `.github/pull_request_template.md`
- `.github/CODEOWNERS`
- `docs/standards/review-and-approval-model.md`

This is how the repo forces the author to distinguish design evidence from
rollout evidence.

## Minimum Governance Artifacts

For a fully governed production-impacting change, the expected evidence set is:

- owning source or platform commit
- validation result
- release candidate bound to the source bundle and build output
- structured stage or pre-prod verification evidence
- approval decision bound to the exact verified candidate
- recorded post-promotion prod smoke or UAT when the product has a real live
  prod surface that should be exercised
- ADR when design changed
- change record when live governed state changed
- approved image digest or host-state evidence
- Argo or host reconciliation evidence
- one real functional verification result

## Candidate-First Governed Delivery Pattern

For a fully governed product with a rehearsal environment, prefer an explicit
candidate-first release model:

- desired source pins in the environment contract
- recorded `release-candidate.yaml` for the built artifact
- recorded `verification.yaml` for rehearsal evidence
- recorded `promotion-readiness.yaml` for the approval decision
- recorded `prod/verification.yaml` for post-promotion smoke or UAT when the
  product exposes a real prod user or operator surface
- promotion that consumes the approved candidate instead of rebuilding a second
  artifact for prod

This pattern keeps build identity, verification evidence, approval, and
promotion reviewable in Git instead of burying them in controller-side memory.

## Anti-Patterns

These are governance failures:

- using a change record to explain architecture
- using an ADR as rollout evidence
- merging a design change without an ADR
- shipping a production-impacting fix without a change record
- treating reconciliation-only checks as complete prod acceptance for a
  user-facing product
- documenting implementation but not decision or evidence
