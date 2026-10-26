---
security_evidence:
  review_areas: [runtime, ai]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console startup provider-version alignment

## Summary

- Date: 2026-10-27.
- Environment: Existing local dev-integration Console composition.
- Change: Align six existing active Ollama bindings with observed runtime0.40.11, retaining the exact qwen3:8b digest and all existing authority.
- Landing Unit Decision: feature_single_landing_unit; maintenance-console-startup-runtime-alignment. The data and operator-document correction share one Platform source, review, commissioning and rollback boundary.

## Classification

- Type: runtime configuration drift; existing provider integrity checks correctly refuse a changed version.
- User-facing impact: complete Console startup cannot pass its mandatory source-realization readiness check.

## Ownership And Review

- Owner: platform-engineering; owner-repo recovery maintenance outside an active ART initiative.
- Security: [Startup provider-version delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-27-console-startup-runtime-alignment.md), followed by exact composed-decision source/tree acceptance and the generated owner-record index.
- Continuity and final evidence: Existing workspace-governance memory learning PR314; no new ART item, candidate, service or architecture version.

## Root Cause

A delayed, dependency-ordered normal activation completed all five profiles. Its final readiness requires source-realization-v1 to be ready. The native gateway returned active/eligible but ready=false with provider-integrity-failed. A bounded metadata-only query from that same gateway observed Ollama0.40.11; all six selected bindings still required0.40.8. The installed qwen3:8b digest matches the accepted500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41. This is explicit runtime drift, not proof of corrupted source or model bytes.

The delayed run retained at least12264MiB available with zero swap use and zero memory-pressure stalls. It still recorded one additional native Python segmentation fault. Provider drift explains a mandatory readiness refusal; it does not explain those cross-runtime native faults or establish that timing is their cause. Direct blob-content checks of202 composition/runner/profile files matched Git. Bounded current database logs showed no corruption/panic signal; this is not a full database integrity scan.

An earlier manual controller stop interrupted Temporal's owner upgrade/rollback. The existing native Helm rollback restored the exact last deployed revision320 as revision323, with no pending releases or deleted history. No generic state deletion or readiness override was used. The operator instruction now requires allowing an in-flight owner upgrade/rollback to finish before stopping a later retry.

## Source Changes

- Update only the six active local Ollama runtime-version fields from0.40.8 to0.40.11 and their current component documentation.
- Preserve provider route, full model digest, callers, purpose/task contracts, data scope, limits, permissions, model-management registrations and configured routing/fallbacks.
- Correct the earlier retry documentation: three starts per ten-minute window is a rate limit, not a lifetime attempt cap. Existing systemd policy and executable code are unchanged.
- Add the concrete metadata/version-drift diagnosis to the existing primary complete-runtime procedure. No new operator command is introduced.

## Artifact And Deployment Evidence

Full local CI-equivalent make validate passed with the canonical OOS source root, including profile/adapter, Console, lifecycle, controlled proof and infrastructure checks. This remains a source-stage record: require exact-head hosted CI/review, then land Security acceptance before advancing the watched main checkout. Commission through the existing complete-runtime command. Prove all six profile metadata-readiness results, current composed status, credential consumption/renewal, authenticated Console owner/current/history/model projections and the original LittleList records. No model inference is needed to verify metadata integrity.

Keep the existing native fault evidence and memory candidate open until the approved operating outcome is actually demonstrated. A corrected version field, healthy homepage or source-clean receipt does not certify a crash-free PC or reliable boot recovery.

## Rollback

Restore the prior reviewed Platform source and paired Security decision as a unit; that version intentionally remains unready against the newer daemon. Preserve owner state, credentials/account history and application data. Do not silently downgrade the provider, widen accepted versions or bypass the exact integrity comparison.

## Live Verification

- Native pre-change metadata: source-realization profile active/eligible but unready; observed daemon0.40.11 versus accepted0.40.8, expected model digest matched.
- Post-change operating proof: pending exact source landing, Security acceptance and normal commissioning; no claim of current complete-runtime acceptance.
- Retained evidence: private Console recovery artifacts and the same memory learning PR314; original owner data/history preserved.

## Follow-Up

- Owner: platform-engineering.
- Required: exact source/CI/review, Security delta/index, normal native readiness/renewal/history proof and source cleanup.
- Native segmentation-fault root cause remains unverified; keep it distinct from this demonstrated version drift and do not invent a new architecture to close this record.
