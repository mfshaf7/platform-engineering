---
security_evidence:
  review_areas: [identity, delivery, runtime]
  findings: []
  risks: []
  workstreams: [WS-007]
  reviewed_artifacts:
    - security-architecture/docs/reviews/components/2026-10-15-bounded-source-realization-boundary.md
  notes: "Approved corrective maintenance. Exact composed acceptance and generated Security index follow actual owner merges; no runtime or app acceptance is claimed by source tests."
---
# Native owner Publication source freshness

## Summary

- Date: 2026-10-23
- Short title: extend existing attributed source visibility and maintenance admission
- Environment: source-only, local dev-integration qualification
- Severity: required repair of the existing Console end-to-end acceptance path

## Classification

- Type: bounded workflow/source-evidence maintenance for Epic1275/acceptance1298
- User-facing impact: newly registered product source can be resolved by normal
  Publication without manually adding owner mounts; maintenance admission no
  longer confuses the historical fixed Inventory blob with current active data

## Ownership

- Owning repo or layer: platform-engineering
- Related repos: workspace-governance, OOS, WGCF, Console, Security Architecture
- Related ADR: existing source-intent credential effects ADR-029; no new service

## Root Cause

- Immediate failure: physical source snapshots have no fresh canonical-main
  attribution; maintenance CLI still requires its original Inventory digest
- Actual root cause: native registration advanced data while these consumers
  retained presence-only and original-data assumptions
- Why it escaped earlier controls: one configured legacy publication owner and
  injected proof did not exercise the newly promoted source-owner route

## Source Changes

- Repo: platform-engineering
- Commit(s): pending Gary exact-head review at authoring
- Guardrail added: fixed-host bounded anonymous public identity/main observer;
  existing marker gets expiring attribution only for registered active product
  owners; same-binding timer reuse never renews age or reclones source;
  failed remote observation invalidates freshness but preserves physical source
- Guardrail added: maintenance CLI proves clean/current WG primary and exact
  original provider, then reuses canonical record admission from committed data
  and schemas; rechecks immediately before minting; original legacy-core scope
  and immutable-blob recovery remain, new owners retain native source-intent
  installation/approval/session/revocation controls
- Test: positive/negative anonymous-provider, real Git CLI promotion/denial,
  native clone attribution, expiry, same-source reuse, dirty-state preservation
- Runbook: complete-runtime source attribution and shared Agent source identity

## Artifact And Deployment Evidence

- Build workflow run: pending exact committed full local/provider CI
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: normal composed activation only after exact
  OOS, WGCF, Console, Platform and Security sources are accepted together
- Why it was environment drift instead of source defect: not environment drift;
  durable consumer behavior needed extension, not a restart or host rewrite
- Recovery command or procedure: existing complete-runtime operator procedure

## Live Verification

- App health: not claimed; Little List import and native graduation still pending
- Deployed image: None; no partial activation
- Pod: None changed by this source Landing Unit
- Functional verification: focused local tests, exact committed full CI and
  native consumer conformance required before activation; actual Console proof
  remains the terminal acceptance, not these isolated tests
- Residual risk: public synthetic qualification only; provider outage/rate
  limits fail closed; this does not admit private/client source or execute apps

## Follow-Up

- Required follow-up: exact owner merges, native producer/consumer proof,
  generated Security index and composed acceptance, normal activation, actual
  original Console business journey and exact owned-resource retirement
- Optional hardening: None added outside the accepted repair boundary
- Owner: Platform; Security and product/workflow owners retain their authority
