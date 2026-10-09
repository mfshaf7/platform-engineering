---
security_evidence:
  review_areas:
    - runtime
    - ai
    - delivery
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - docs/components/governed-ai-gateway/README.md
    - docs/components/governed-ai-gateway/architecture.md
    - scripts/test_ai_model_profiles.py
  findings: []
  risks: []
  workstreams:
    - WS-007
  notes: The update accepts the observed Ollama patch runtime only after exact model-digest, synthetic Agent Console invocation, and strict response-schema compatibility proof; no provider, model, caller, data, or action authority changes.
---

# Governed AI Runtime 0.40.1

## Summary

Updates the local `dev-integration` governed AI profiles from Ollama 0.32.15
to the observed host runtime 0.40.1 while retaining the exact reviewed
`qwen3:8b` model digest and every existing trust-boundary restriction.

## Classification

- area: governed AI gateway provider integrity
- type: host/environment drift reconciliation
- runtime impact: the gateway may invoke the already selected local model only when the host reports exactly Ollama 0.40.1

## Ownership

- owner repo: `platform-engineering`
- related ART slice: #1246 under Feature #1215 and Epic #1203
- related products or components: governed AI gateway and Governance Operations Console

## Root Cause

- immediate failure: the Agent Console gateway allowed the request but rejected provider invocation with `provider-integrity-failed`.
- actual root cause: the Windows Ollama desktop runtime advanced to 0.40.1 while all active local provider bindings still pinned the earlier reviewed 0.32.15 patch.
- why it escaped earlier controls: source validation proved exact configured pins but no pre-proof check reconciled the live host patch version with those pins.

## Source Changes

- changed workflow, adapter, or contract: update all active local Ollama binding pins and current architecture documentation to 0.40.1.
- tests or validator added: assert all active local Ollama bindings share the exact reviewed runtime version.
- related change records: `docs/records/change-records/2026-10-09-agent-console-platform-admission.md`

## Artifact And Deployment Evidence

- source-only change, or build/deployment evidence: owner-repo maintenance Landing Unit `maintenance/governed-ai-runtime-0-40-1`
- image tag or digest: None; the existing local composition renders the profile registry into its gateway runtime
- runtime revision: host Ollama 0.40.1 with `qwen3:8b` digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`

## Live Verification

- local validation: Platform profile, runtime, repository, documentation, and base-aware change-record validators
- live or dev-integration verification: bounded compatibility invocation returned strict-schema-valid output on Ollama 0.40.1; rebuild the existing composition and repeat #1246 operating proof
- residual risk: any future runtime or model digest change continues to fail closed and requires a fresh exact review

## Follow-Up

- required follow-up: bind Security acceptance to the exact Platform merge and close the linked improvement candidate only after live #1246 proof succeeds
- owner: `platform-engineering`
- due date or closure condition: before Feature #1215 and Epic #1203 close
