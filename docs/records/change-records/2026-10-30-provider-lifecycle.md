---
security_evidence:
  review_areas: [runtime, delivery, ai]
  reviewed_artifacts:
    - dev-integration/profiles/governed-ai-gateway/runtime/model_management.py
    - dev-integration/profiles/governed-ai-gateway/runtime/gateway_app.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/console_model_management.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Separate Console core readiness from provider availability

## Summary

Operator-authorized maintenance restores ADR-030's management/provider boundary.
Landing Unit Decision: feature_single_landing_unit, maintenance-provider-lifecycle-platform-20261030.
The existing owner API, Model Operations and observation timer are extended.

## Classification

Corrective maintenance of existing local dev-integration behavior; no new ART,
registry, daemon, provider permissions or browser credential authority.

## Ownership

Platform owns runtime/health and registration; OOS owns authenticated projections
and immutable requests; Console owns the existing operator interface. Security
retains [exact acceptance](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-30-provider-lifecycle.md).

## Root Cause

The complete runtime required the legacy source-realization Ollama binding even
when runtime routing already selected a registered hosted primary. Provider
metadata drift therefore blocked core recovery. Registry reads also exposed no
current provider observations, leaving users without a direct update path.
The existing verified registration command already supports stable-ID updates.

## Source Changes

Core startup checks the owned management plane, not an unused legacy model.
After a same-boot core success signal, the existing timer checks only registered
providers without inference, project context or configuration mutation. Cached
observations bind the configuration revision/digest and expire after 120 seconds.
Invalid, missing, stale or concurrent-edit evidence means unknown health without
removing management controls. Metadata drift requires explicit existing
model.register verification; stable model IDs, route choices and history remain.
Codex account presence does not assert remote connection or entitlement; routine
checks do not launch Codex. Invocations retain strict integrity, permission,
completion-uncertainty and ordered pre-submission fallback controls.

Registry health is opt-in (`include_health=true`) so the preceding strict Console
consumer retains its exact response shape during staged owner replacement.

## Live Verification

Owner checks cover provider loss/drift, expiry, invalid evidence, first use,
same-boot post-core ordering, no inference and preserved configuration. Exact
committed local CI-equivalent checks and hosted checks precede delegated review.
Native core startup, Console provider visibility and unchanged routing still
require accepted composition; this record is not a runtime completion claim.

## Artifact And Deployment Evidence

Exact merged sources and Platform tree must be bound by the composed Security
decision. The owned managed adapter image is retained; ordinary registered-model
updates do not require static source version changes.

## Rollout And Rollback

Land backward-compatible OOS, Platform, Console, then exact Security acceptance.
Use normal complete-runtime activation, retaining data, original durable
generation, accounts and histories. Existing Platform rollback owns runtime
restoration. Health evidence is disposable and never an invocation authorization.

## Follow-Up

Retain native evidence and clean exact Landing Unit credentials, worktrees and
branches after proof. No new feature or improvement item is requested.
