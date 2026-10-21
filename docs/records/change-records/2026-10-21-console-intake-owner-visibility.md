---
security_evidence:
  review_areas: [delivery, runtime, ai]
  findings: []
  risks: []
  workstreams: [WS-005, WS-007]
---

# Console physical owner source visibility

## Summary

- Date: 2026-10-21.
- Short title: connect completed native bootstrap to physical Intake readiness.
- Environment: local dev-integration only.
- Severity: admission and interruption recovery blocked; no canonical loss.
- Landing Unit: maintenance-1275-intake-owner-visibility;
  child_isolated_landing_unit for Platform's composition/rollback boundary.
- Tracking: existing Epic1275/1298 and operating-truth regression candidate;
  operator-approved maintenance, no repair ART child.

## Classification

- Type: deployment/source visibility handoff bug and host runtime version drift.
- User-facing impact: host bootstrap succeeds but WGCF cannot see the owner;
  later host update makes normal restart fail before OOS comes up.

## Ownership

Platform owns read-only source projection and exact runtime bindings. WGCF owns
the exact-root Git probe. WG owns Intake/Inventory; OOS owns bootstrap/readiness
orchestration; Security owns exact-source acceptance. No boundary is reassigned.

## Root Cause

- Immediate failure: native readiness receipt7929c895 denies physical presence
  although bootstrap10cf retained a clean actual owner checkout at d48e597d.
- Actual root cause: only three static source roots were mounted into WGCF.
  Host presence did not imply container presence. Native UID10001 also rejects
  foreign-owned Git; that exact probe is repaired in its WGCF owner.
- Why it escaped earlier controls: composed qualification stopped before the
  actual proposed-to-admitted transition after real bootstrap.
- Interruption: native Windows Ollama reports0.40.7, six active bindings pin
  0.40.6, gateway readyz reports provider-integrity-failed. Selected qwen3:8b
  digest500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
  is unchanged. Missing OOS executor mount is downstream of incomplete startup,
  not an independently proven source defect or a memory-pressure diagnosis.

## Source Changes

- Repo: platform-engineering.
- Commit(s): exact reviewed PR head and actual merge recorded by provider.
- Guardrail added: real-Git producer tests, actual mount/status/rollback tests,
  primary runbook. Existing six Ollama version fields update to0.40.7 only.
- Extend the existing snapshot refresh: bounded canonical source-only entrants
  and active owners, direct physical checkout, regular controls, exact provider,
  clean main and origin/main match. Expose sanitized committed Git snapshots
  through one fixed read-only parent, never live app roots or ignored data.
- Obsolete attributed snapshots move outside visibility; unique/dirty state is
  preserved and denied. No new daemon, request, model, permission, code-execution
  authority, global Git trust or canonical-workspace mutation is introduced.

## Artifact And Deployment Evidence

- Build workflow run: actual required Platform PR CI before merge.
- Published image tag/digest: None for Platform; host-side source.
- Recorded prod revision/Argo revision: None; stage/prod out of scope.
- Ordered landing: WGCF probe, Platform source/tree, exact existing Security
  decision and generated owner-change index, then normal activation.

## Host Or Runtime Recovery

- Required host/runtime action: stop the failing dedicated supervisor retry,
  preserve all persisted state, land/reaccept the exact source, normal activate.
- Why environment drift: actual Ollama host version advanced; no model changed.
  The separate visibility/probe defects require durable owner source repair.
- Recovery command: existing governance-console-complete-runtime activation;
  do not edit private policies, invent admission data or recreate bootstrap.

## Live Verification

- App health: not proved by this repair. Little List app transfer is pending.
- Deployed image/pod: actual accepted composition readback after source landing.
- Functional verification: required native distinct-UID committed-source probe,
  current gateway/OOS/services, corrected actual Console admission then Inventory.
- Residual risk: new source-only/public synthetic route only; no private/client,
  hostile-source, public-hosting, stage/prod or arbitrary project qualification.

## Follow-Up

- Required: exact source review/CI, Security/tree/index, normal commissioning,
  real same-product Console transition and application delivery.
- Optional hardening: None proposed in this repair.
- Owner: mfshaf7; due before qualification1298 completion.
