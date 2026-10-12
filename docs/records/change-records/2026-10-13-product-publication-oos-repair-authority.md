# Product Publication OOS Repair Authority

## Summary

The Product Publication commissioning policy now pins the exact OOS head that
contains the reviewed monotonic workflow-projection and Workspace Inventory
history-readback repairs. The strict source gate remains exact and fail closed.

## Classification

- area: Governance Operations Console Product Publication commissioning
- type: corrective owner-repo maintenance
- runtime impact: activation accepts one newly reviewed OOS source revision

## Ownership

- owner repo: `platform-engineering`
- related delivery scope: Product lifecycle maintenance under #1273
- Security review: `security-architecture/docs/reviews/components/2026-10-13-product-publication-oos-repair-delta.md`
- tracking record: `workspace-governance/reviews/improvement-candidates/2026-10-12-product-publication-activation-ownership-regression.yaml`

## Root Cause

OOS evidence-integrity repairs merged after the commissioning policy had pinned
the previous activated OOS revision. The exact-source control correctly denied
the newer runtime head, but the repair landing sequence did not reconcile that
dependent pin before reporting the repair complete.

## Source Changes

- advance only `owners.oos.revision` from `2bb5155` to the Security-reviewed
  repair head `94534d6`
- update the policy assertion to preserve the exact revision requirement
- keep the original lifecycle Security decision URI, digest, approved targets,
  denied targets, identities, and owner boundaries unchanged

## Artifact And Deployment Evidence

- OOS repair source: pull requests #320 and #321
- Security repair review: pull request #239, merged as `2a25333`
- Platform landing unit: `delivery-894-oos-repair-authority`
- rollback: revert this exact policy revision to restore the prior OOS pin

## Live Verification

- Product Publication policy tests and repository validation must pass locally
  and in exact-head CI
- `ACTION=validate` and `ACTION=activate` must accept the clean reviewed OOS
  `94534d6` checkout without weakening the source comparison
- final sequence and operating acceptance remain owned by #1273

## Follow-Up Actions

- complete the existing Product Publication and Workspace Registry round trip
- close the linked improvement candidate only after #1273 final reconciliation
