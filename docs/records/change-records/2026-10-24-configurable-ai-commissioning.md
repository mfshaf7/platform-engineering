---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime, ai]
  reviewed_artifacts:
    - products/governance-operations-console/complete-runtime-policy.yaml
    - products/governance-operations-console/scripts/console_model_management.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - dev-integration/profiles/governed-ai-gateway/scripts/common.sh
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: Source-staged commissioning candidate for exact Security1319 review; deployment and operating qualification remain separate evidence.
---

# Configurable AI commissioning

## Summary

- Date: 2026-10-24
- Short title: Commission configurable model operations in the existing Console composition
- Environment: local dev-integration only
- Severity: planned capability extension

## Classification

- Type: reviewed runtime and provider-account integration
- User-facing impact: Console model registration and workflow routing become available only after the exact composed Security decision and commissioning.

## Ownership

- Owning repo or layer: Platform Engineering, ART #1320 under Epic #1313
- Related repos: OOS #1317, Console #1318 and Security #1319
- Related ADR: [ADR-030](../../decisions/adr/ADR-030-configurable-ai-task-routing.md)

## Root Cause

- Immediate failure: None; this is the planned commissioning unit after inactive owner-source implementation.
- Actual root cause: Source implementation alone does not provide the accepted image, scoped account lease, network/resource controls or management connection.
- Why it escaped earlier controls: Not applicable; these are explicit remaining deliverables in the accepted architecture.

## Source Changes

- Repo: platform-engineering
- Commit(s): exact candidate and merged tree are bound by the Review Packet and Security decision; no future merge identifier is fabricated here.
- Guardrail added: admitted composition tests, actual native image digest validation, Kubernetes server dry-run and the primary complete-runtime procedure.
- Security authority: [exact composed AI review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md); source remains pending until that decision accepts the actual candidate tree.

## Artifact And Deployment Evidence

- Build workflow run: source-local proof and the exact PR check are recorded in the Review Packet.
- Published image tag: local tree-derived gateway image; the executable and base image digests are fixed in the source policy.
- Published digest: actual local image identity is recorded during source/runtime qualification.
- Recorded prod revision: None; no stage or production activation.
- Argo application revision: None; the existing dev-integration runner owns this composition.

## Host Or Runtime Recovery

- Required host/runtime action: use the existing complete-runtime activation after Security acceptance, then the Console's dedicated account sign-in.
- Why it was environment drift instead of source defect: Not applicable.
- Recovery command or procedure: [Operate the complete Console runtime](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).

## Live Verification

- App health: not claimed by source validation.
- Deployed image: not claimed before exact-source activation.
- Pod: no deployment is implied by the source candidate or server dry-run.
- Functional verification: #1321 must supply real Console configuration, native provider invocations, selection evidence and recovery proof across the current profiles.
- Residual risk: private-client custody, stage/prod, direct-provider clients and model tool/action authority are outside this acceptance.

## Follow-Up

- Required follow-up: exact Security acceptance, source merge, commissioning, #1321 operating evidence and generated-index/owned-resource cleanup.
- Optional hardening: None invented for this delivery.
- Owner: Platform Engineering; Security retains its own acceptance authority.
