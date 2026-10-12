---
security_evidence:
  review_areas:
    - runtime
    - secrets
    - delivery
  reviewed_artifacts:
    - scripts/workspace_intake_identity.py
    - scripts/test_workspace_intake_identity.py
    - docs/components/operator-orchestration-service/workspace-intake-identity.md
  findings: []
  risks: []
  workstreams:
    - WS-007
  notes: The pod-template annotation contains only the non-secret token expiry already permitted in receipts and forces a bounded OOS rollout for each newly issued token.
---

# Workspace Intake Token Rotation Consumption

## Summary

Workspace Intake credential delivery now changes the OOS pod template for every
new token and waits for that generation to roll out. A delivery receipt can no
longer report success while the running OOS pod still reads the prior projected
token file.

## Classification

- area: Workspace Intake and Inventory runtime identity
- type: corrective owner-repo maintenance
- runtime impact: each delivery or rotation performs one bounded OOS rollout

## Ownership

- owner repo: `platform-engineering`
- related delivery scope: Product lifecycle maintenance under #1273
- tracking record: `workspace-governance/reviews/improvement-candidates/2026-10-12-product-publication-activation-ownership-regression.yaml`

## Root Cause

The delivery path updated the Kubernetes Secret, then applied a pod-template patch
whose content was unchanged across rotations. Kubernetes therefore had no new
Deployment generation to roll out, and OOS could briefly continue reading the
expired token even though Platform had already emitted a successful delivery
receipt.

## Source Changes

- stamp the issued token's non-secret expiry on the OOS pod template
- retain the existing rollout wait so command success proves the new generation is ready
- document and test that two token expiries produce distinct deployment patches

## Artifact And Deployment Evidence

- source landing unit: `product-lifecycle-workspace-intake-token-consumption`
- runtime delivery: existing Workspace Intake identity `deliver` action and OOS Deployment rollout
- rollback: revert the owner-repo merge; previously issued short-lived tokens retain their normal expiry and revocation behavior

## Live Verification

- local validation: identity unit tests, repository validation, and base-aware change-record validation
- dev-integration proof: rotate the Workspace Intake identity and reconcile the already-merged Product lifecycle request without a manual rollout
- residual risk: rotation intentionally restarts the single local OOS replica; durable workflow state remains outside the pod

## Follow-Up

- linked candidate: `workspace-governance/reviews/improvement-candidates/2026-10-12-product-publication-activation-ownership-regression.yaml`
- closure condition: merged source and successful rotation-plus-lifecycle continuation
