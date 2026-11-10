---
security_evidence:
  review_areas: [ai, delivery]
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - security/governed-ai-access-plane.yaml
    - security/schemas/source-editor-assistance.schema.json
    - dev-integration/profiles/governed-ai-gateway/runtime/model_configuration.py
  findings: []
  risks: []
  workstreams: [WS-007]
---

# Source editor assistance contract

## Summary

Extends the shared source workspace with an explicit, source-aware AI proposal path.

## Classification

Operator-approved extension outside active ART, retained in the unpublished preview batch. The recorded owner Landing Unit and dependency boundaries apply.

## Ownership

Console owns presentation; OOS owns session, context and draft orchestration; Platform owns model policy and runtime; Security retains acceptance.

## Root Cause

The previous editor exposed basic text editing and a separate generation action, with no selected-file conversation and iterative proposal review. This is an approved capability extension, not a fabricated historical contract defect.

## Source Changes

Operator-approved extension of the two existing source profiles. Landing Unit
Decision: child_isolated_landing_unit, source-editor-assistant-platform-20261109.
Platform source/policy rollout and rollback are separate from OOS and Console.
No new provider, account, source-execution authority or infrastructure is added.

Both source profiles admit the bounded `source_editor_assistance` task and its
message-plus-selected-file proposal schema. Callers remain unchanged. Source
assistance inherits the corresponding source-generation routing override before
the normal default; an explicit assistant-task selection takes precedence.
Configured model, effort, permission and fallback validation remain active.

The source editor can discuss or propose edits, but the model cannot save,
execute, commit, approve, publish, merge or activate source. OOS retains path,
base/digest, context and proposal validation. UI review, model-policy tests and
routing inheritance tests are source evidence, not live model qualification.

This branch remains in operator preview. Fresh composed Security acceptance
and coherent OOS/Console/Platform source activation are required before normal
live use. Existing account/provider state and the current gateway stay unchanged.
The existing accepted composition is the rollback; no state migration occurs.

## Artifact And Deployment Evidence

Implementation and isolated tests are recorded with the owning source batch; no deployment or account changes have been performed.

## Live Verification

Preview only. Live commissioning and native provider/source qualification remain pending exact composed acceptance.

## Follow-Up

Complete operator visual review, owner source publication, Security delta/index and exact acceptance before normal Platform activation. Keep the previous accepted live composition until then.
