---
security_evidence:
  review_areas: [ai, runtime]
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - dev-integration/profiles/governed-ai-gateway/runtime/ollama_adapter.py
    - dev-integration/profiles/governed-ai-gateway/runtime/model_configuration.py
    - scripts/test_ai_task_routing.py
    - scripts/test_governed_ai_ollama_adapter.py
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: "Source review; exact composed acceptance, activation and native advisor qualification remain separate."
---

# Work Design reasoning allowance and local context admission

## Summary

Operator-approved maintenance extends the existing Context and Build Tree
reasoning allowance from 120 to 600 seconds. Landing Unit Decision:
`feature_single_landing_unit`,
`maintenance-work-design-reasoning-runtime-20261118`. Publication was approved
after preview review. Existing model selection, dedicated account custody,
single native provider slot and explicit final operator authority remain.

## Classification

Existing local dev-integration advisor maintenance; no new service or ART scope.

## Ownership

Platform owns provider limits and local admission; OOS/CGG/Console retain their
existing workflow, context and presentation responsibilities. Security retains
exact composed acceptance.

## Root Cause

The short provider allowance ended detailed architecture requests without a
confirmed result. The paired context and renderer guidance also needed repair;
raising reasoning effort alone cannot resolve those independent constraints.

## Source Changes

Only the existing Work Design profile gets the longer provider budget. The
paired OOS/Console deadlines enclose it. Existing Model Operations supplies
explicit independently selected Extra High overrides after activation; no
provider or unrelated route is selected by this source change.

The local Ollama context stays 4096 tokens. A conservative input-size preflight
refuses clearly oversized complete requests before any provider access instead
of silently dropping architecture or increasing memory. This is not a tokenizer
guarantee. The routing journal retains the capacity outcome; pre-submission busy
or input refusal does not overwrite successful model-health evidence. Configured
fallback remains pre-submission only; uncertain completion never dispatches a
second inference.

## Artifact And Deployment Evidence

Local adapter, routing, gateway and registry checks precede publication. Exact
CI results and reviewed heads bind the source PR. The fresh
[Security delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-18-work-design-reasoning.md)
and exact composed decision precede normal complete-runtime activation. Native
Context/Build Tree quality and elapsed-time evidence remain operating proof,
not consequences of passing synthetic tests. No Stage/Prod claim is made.

## Live Verification

No new source has been activated yet. After merged-source acceptance, inspect
normal lifecycle status and prove detailed native advice from both workflows.

## Follow-Up

Complete exact-head review, source acceptance, normal activation and native
qualification; revoke the exact maintenance grant and retire source residue.

## Rollback

Select the preceding accepted owner sources and run their normal lifecycle.
Preserve account custody, model configuration, unknown invocation journals,
private drafts and canonical work. No new service, queue or ART item is added.
