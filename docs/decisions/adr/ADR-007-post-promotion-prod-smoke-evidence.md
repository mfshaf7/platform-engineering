# ADR-007: Post-Promotion Prod Smoke Evidence For Fully Governed Products

## Status

- Accepted

## Context

- The candidate-first OpenClaw workflow already makes stage rehearsal,
  verification, and promotion approval explicit in Git.
- The remaining gap was production acceptance: prod promotion could be fully
  reconciled and attested at the Argo or image level without a dedicated
  post-promotion functional smoke or UAT record.
- For a user-facing product such as OpenClaw, reconciliation alone is weaker
  than enterprise-grade rollout evidence. The workflow needs an explicit answer
  to:
  - what exact prod candidate is live
  - which prod smoke or UAT checks were executed
  - who performed them
  - where the evidence lives
- The goal is to tighten production evidence without rebuilding a second
  approval lane after stage. Stage remains the promotion gate; prod smoke is
  the post-cutover completion proof.

## Decision

- For a fully governed product that exposes a real prod user or operator
  surface, post-promotion prod smoke or UAT must be recorded explicitly in a
  Git-managed verification object bound to the current prod contract.
- The reference pattern is:
  - stage `release-candidate.yaml`
  - stage `verification.yaml`
  - stage `promotion-readiness.yaml`
  - prod `verification.yaml`
- Promotion must reset the prod verification object to `pending` for the newly
  promoted contract.
- A rollout is not operationally complete until the required prod smoke or UAT
  checks are recorded for that exact prod candidate.
- The baseline prod check set should be intentionally narrower than stage:
  - reconciliation state
  - one real primary user-path smoke
  - one read-only prod operator-surface smoke when that surface exists
- This becomes the reference pattern for future fully governed user-facing
  products, while remaining optional for products that do not expose a real prod
  surface worth exercising.

## Consequences

- Production evidence is clearer and closer to real enterprise QA or UAT
  expectations for user-facing products.
- Promotion remains candidate-first and immutable; prod smoke does not weaken
  the stage approval gate or trigger a rebuild.
- Operators must perform and record one more explicit post-promotion step before
  calling the rollout complete.
- Product templates, runbooks, and controller logic must preserve the prod
  verification object when a product adopts this pattern.
- No change record is required for this ADR itself because it changes workflow
  doctrine and tooling, not live governed state. Future live promotions should
  capture the governed rollout evidence in product-specific change records when
  required.

## Alternatives Considered

- Option: Treat Argo reconciliation plus runtime startup as sufficient prod acceptance.
  - Rejected because it is too weak for a user-facing Telegram product and does
    not prove that real prod interactions succeeded.
- Option: Re-run the full stage verification pack in prod.
  - Rejected because it is unnecessarily broad and risky; stage remains the
    primary rehearsal lane for higher-risk checks.
- Option: Keep prod acceptance only in runbook prose or chat notes.
  - Rejected because it is not reviewable, machine-checkable, or durable.
