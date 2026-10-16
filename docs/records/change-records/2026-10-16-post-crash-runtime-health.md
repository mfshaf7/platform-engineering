---
security_evidence:
  review_areas: [runtime, ai, delivery]
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - dev-integration/profiles/governed-ai-gateway/runtime/gateway_app.py
    - dev-integration/profiles/governed-ai-gateway/runtime/ollama_adapter.py
    - products/governance-operations-console/scripts/console_record_authority.py
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: Explicit operator-approved 0.40.5 patch reconciliation; exact model digest, invocation integrity, data-source admission and freshness expiry remain enforced. Metadata readiness performs no inference.
---

# Post-crash Console runtime health

## Summary

- Date: 2026-10-16
- Short title: reconcile actual provider version and uninterrupted unchanged record freshness
- Environment: local dev-integration only
- Severity: governed AI blocked; transient canonical-read failures

## Classification

- Type: host/environment drift and existing runtime-readiness implementation repair
- User-facing impact: AI calls rejected the installed patch while readiness appeared green; unchanged snapshot refresh briefly removed authority.

## Ownership

- Owning repo or layer: platform-engineering
- Related repos: operator-orchestration-service and security-architecture
- Related ADR: None; extends existing provider and snapshot controls without new architecture

## Root Cause

- Immediate failure: provider integrity rejected Ollama 0.40.5 against approved 0.40.1; routine refresh exposed a missing checkpoint.
- Actual root cause: readiness observed policy eligibility rather than the provider; refresh unlinked a valid checkpoint before every network fetch, even when the record revision was unchanged.
- Why it escaped earlier controls: static profile tests did not prove actual readiness and native snapshot tests inspected only completed refreshes.

## Source Changes

- Repo: platform-engineering
- Commit(s): exact reviewed Landing Unit maintenance-1275-runtime-health-platform
- Guardrail added: metadata-only provider version/digest readiness with bounded timeouts and shared-binding deduplication; native unchanged-refresh continuity, failure denial and symlink-safe invalidation tests.

## Artifact And Deployment Evidence

- Build workflow run: exact-head CI required before merge
- Published image tag: existing rendered Gateway and Console composition; no new image family
- Published digest: exact accepted Platform tree is bound by Security
- Recorded prod revision: None; local-only
- Argo application revision: None; no stage/prod reconciliation

## Host Or Runtime Recovery

- Required host/runtime action: operator restarted Docker; keep installed Ollama 0.40.5 and exact qwen3:8b digest.
- Why it was environment drift instead of source defect: provider patch drift is environmental; misleading readiness and checkpoint interruption are source defects repaired in their existing owners.
- Recovery command or procedure: existing make governance-console-complete-runtime ACTION=activate only after exact Security acceptance; no private-policy edits or invocation-integrity bypass.

## Live Verification

- App health: actual metadata and bounded synthetic model invocation required after source acceptance, not claimed from tests.
- Deployed image: existing admitted runtime composition
- Pod: discover current owner pods during activation rather than pinning disposable names.
- Functional verification: repeated canonical reads across refresh and a direct Delivery register read after OOS batching.
- Residual risk: later provider updates still fail closed; record advancement may briefly deny reads while canonical source changes. Unchanged refresh must not withdraw valid authority.

## Follow-Up

- Required follow-up: Security review/index, exact-source activation, live proof and source cleanup before completion.
- Optional hardening: None proposed; no new monitor, service or ART child.
- Owner: platform-engineering
