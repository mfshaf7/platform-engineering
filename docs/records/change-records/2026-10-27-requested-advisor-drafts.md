---
security_evidence:
  review_areas: [runtime, ai]
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - security/schemas/delivery-refinement-advice.schema.json
  findings: []
  risks: []
  workstreams: [WS-007]
---

# Bound local advisor drafting within existing profiles

## Summary

- Date: 2026-10-27
- Short title: Give explicit local draft requests a bounded completion window.
- Environment: Existing local dev-integration composition only.

## Classification

Operator-directed advisor maintenance outside Epic1332. Landing Unit Decision:
feature_single_landing_unit, maintenance-advisor-drafts-platform. No new model
profile, route, account, credential, executor, tool permission or final authority.

## Ownership

Platform owns model profiles and runtime commissioning. Console owns local draft
validation/setters; OOS/CGG retain governed workflow/context authority. The paired
[Security delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-27-requested-advisor-drafts.md)
and exact composed decision precede activation.

## Root Cause

The existing60-second completion window ended a real governed diagram request
with provider-completion-unknown. The unchanged original audit identity remains
retained. Local structured diagrams/trees also need more output room than short
answers. Refinement's provider schema forced review although answer-only output
is admitted by its existing owner result contract.

## Source Changes

Existing Work Design, Refinement and Agent Console profiles use120-second
deadlines inside the Console's180-second request bound. Work Design/Agent
Console output caps increase2048 to4096tokens; Refinement retains2048. Context
still enters CGG. Existing source-selected and operator-configured model/effort
routes, dedicated account custody, single native provider slot, unknown-turn
retention and no speculative model fallback remain intact. Refinement advice
admits review/none; OOS enforces null values for answer-only replies.

## Artifact And Deployment Evidence

Source validation and exact reviewed heads belong to the Gary PRs. The existing
finite composed source decision selects the accepted trees, then normal complete
runtime activation applies them. No source-stage deployment claim or new
commissioning mechanism is introduced.

## Live Verification

Model-profile source validator and24 profile tests passed. Full changed-surface
policy/runtime proof, exact composed acceptance and native Console drafting
remain required before operating qualification. Preserve original unknown
invocations; do not delete journals or inject another successful receipt.

## Follow-Up

Complete source review, exact Security acceptance, normal activation and native
Console proof; revoke the exact maintenance credential and retire the branch
and worktree. Rollback restores the preceding accepted source decision and
normal owner composition without deleting account or workflow state.
