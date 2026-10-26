---
security_evidence:
  review_areas: [runtime, secrets, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console prebuilt runtime and memory containment

## Summary

- Date: 2026-10-26
- Short title: Serve the everyday Console from an exact-source standalone artifact.
- Environment: Existing local dev-integration composition.
- Severity: Maintenance; no production incident classification.

## Classification

- Type: deployment/artifact bug.
- User-facing impact: The always-running development compiler retained about8.1GiB of private process memory. Normal Console operation should use prebuilt output while editing retains hot reload in an isolated worktree.
- Landing Unit Decision: feature_single_landing_unit; maintenance-console-prebuilt-runtime-memory. Operator approved the concrete memory plan before the earlier readiness gaps.

## Ownership

- Owning repo or layer: platform-engineering; existing Console composition and host provisioning.
- Related repos: governance-operations-console (unchanged application source), security-architecture (exact acceptance).
- Related ADR: Existing Console complete-runtime architecture; no new component or authority boundary.

## Root Cause

- Immediate failure: The managed everyday frontend launches npm run dev, retaining compiler and hot-reload state in the long-lived process.
- Actual root cause: Development and normal operation share the same runtime mode and source-output directory. A controlled frontend restart reduced the service from8.4GiB to about2GiB after UI compilation; exact heap retention/leak objects remain unproven. Windows VM working set and Linux available memory require separate measurement.
- Why it escaped earlier controls: Functional and source proof did not establish a bounded always-on frontend footprint. This maintenance adds source-bound artifact/service readback and measured budgets; it does not reinterpret uncommissioned features as defects.

## Source Changes

- Repo: platform-engineering.
- Commit(s): Pending reviewed source landing.
- Guardrail added: Exact clean-source standalone export/build, complete static assets, private credential-free build environment, artifact integrity and real process/source readback; isolated development path, bounded compiler/runtime memory and failed-build cleanup. Tests and the existing primary runtime runbook cover the behavior.

## Artifact And Deployment Evidence

- Build workflow run: Local exact Console source build plus Platform CI; acceptance pending.
- Published image tag: None; existing local private standalone artifact, no registry or new service.
- Published digest: Artifact file inventory and selected source/toolchain binding.
- Recorded prod revision: None; local dev-integration only.
- Argo application revision: None; existing managed user service.

## Host Or Runtime Recovery

- Execution correction: During this work, unignored local diagnostics were initially written under the live Platform primary. The existing source-clean gate correctly blocked automatic credential renewal. Evidence was preserved and moved to verified ignored Console custody, the empty old directory removed, and normal renewal restarted. Owner-local `.art/` ignore coverage prevents this capture-path regression; its separate learning signal is tracked in the same closeout Landing Unit. No diagnostic data was staged or published.
- Required host/runtime action: Normal exact Security acceptance and complete-runtime activation; measured WSL budget/reclamation settings require explicit activated readback after any necessary WSL restart.
- Why it was environment drift instead of source defect: Current launch behavior matches the older source; this is an approved runtime-mode extension, not accidental source corruption.
- Recovery command or procedure: Existing complete-runtime operator surface. Preserve private environment, account custody, owner records and the prior artifact. Keep development output outside the served artifact.

## Live Verification

- App health: This source-stage record does not assert operating completion. Final exact-source commissioning, memory and cleanup results belong in the [linked learning closeout](https://github.com/mfshaf7/workspace-governance/blob/main/reviews/improvement-candidates/2026-10-26-console-long-running-development-memory.yaml), avoiding a post-acceptance source-pin loop.
- Deployed image: Existing backend images unchanged.
- Pod: No new frontend pod; existing loopback service.
- Functional verification: Require current owner reads, all existing destinations and Current/History capability, original LittleList history, frontend restart/source readback and warmed memory comparison. WSL active memory, cache, pressure and Windows working set are measured independently.
- Measured build: Exact-source isolated build completed in75.12seconds with a conservative2.54GiB summed process RSS peak and over10GiB guest available. Credential-free standalone preview served root/static assets and used about140MiB; live authenticated proof remains pending. WSL3.0.3 source confirms CPU-idle gating; active workload sampling is distinguished from a separate normal-stack observation. Stage20GiB guest ceiling/6GiB swap from this headroom, preserve existing host settings, and verify activation after restart.
- Residual risk: Restart containment does not prove long-term memory stability; a low arbitrary cap can harm builds. Budget choices require observed headroom. Source review alone is not operating completion.

## Follow-Up

- Required follow-up: Exact Security acceptance and generated change-record index after this owner record lands; existing commissioning and memory/reclaim proof; source cleanup.
- Optional hardening: None proposed.
- Owner: platform-engineering.
