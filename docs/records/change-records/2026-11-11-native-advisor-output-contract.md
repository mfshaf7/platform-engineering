---
security_evidence:
  review_areas: [ai, identity, delivery, runtime]
  findings: []
  risks: []
  workstreams: [WS-007]
  reviewed_artifacts:
    - products/openproject/catalog-control/openproject_delivery_catalog_control.rb
    - products/openproject/catalog-control/test_memberships_native.rb
    - products/openproject/scripts/openproject_provision_identity_runner.rb
    - products/openproject/scripts/openproject_provision_identity.sh
    - products/openproject/openproject-platform-admin-surface.json
    - security/schemas/advisor-draft-reply.schema.json
    - security/schemas/delivery-work-design-advice.schema.json
    - security/schemas/agent-console-response.schema.json
    - scripts/test_native_advisor_schema.py
    - scripts/test_governed_ai_gateway_runtime.py
  notes: "Source/preview only; existing model, effort, caller, admission and approval boundaries remain. Fresh exact composed Security acceptance and live proof are pending."
---

# 2026-11-11 Native advisor output contract

## Summary

- Date: 2026-11-11
- Short title: enforce draft advice as native provider structure
- Environment: local source and preview batch; live remains on accepted source
- Severity: workflow reliability repair

## Classification

### Approved project-membership extension

The operator approved completing Console project-membership management in this
same maintenance preview batch. Reuse OpenProject's existing project membership
authority and services through OOS. Preserve all existing source work. The
Landing Unit remains `feature_single_landing_unit` for this owner, with the OOS
and Console branches as separate owner boundaries. No new ART item is created.
Runtime lane: the existing accepted-idea-delivery dev-integration profile.

Project-specific provisioning may add the non-admin Project membership manager
role (`view_members`, `manage_members`) only to the Delivery project; Proposal
roles and platform-integrated production remain unchanged. Native form/schema
proof precedes implementation of the mutation adapter. Final composed identity
review, native readback/replay proof and operator preview acceptance are required
before source publication/activation. No global account administration, new
identity provider, generic admin proxy, or automatic membership decision is
introduced. Rollback removes only the added role and restores the prior adapter.
The additive Security source review is
[Console project membership](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-17-console-project-membership.md).

- Type: existing bounded AI output-contract repair
- User-facing impact: malformed nested prose/JSON can no longer satisfy the model output schema as a successful diagram draft
- Landing Unit Decision: `feature_single_landing_unit`, `maintenance-advisor-output-contract-20261111`

## Ownership

- Owning repo or layer: Platform governed model output schemas
- Related repos: OOS semantic decoding/work guides, CGG complete draft projection, Console local context/transaction and diagram UI, Security composed acceptance
- Related ADR: existing ADR-021 multi-profile governed AI gateway; extend its typed output boundary without a new service

## Root Cause

- Immediate failure: Work Design responses used unsupported patch arrays, omitted intent or returned ordinary prose
- Actual root cause: the provider grammar constrained outer metadata and text, leaving the edit object as unconstrained string content
- Why it escaped earlier controls: wrapper-schema proof did not require the native local edit transaction shape

## Source Changes

The existing Agent Console and Work Design provider schemas require a native
`draft_reply` object. Text, board and tree payloads have closed properties and
bounded arrays/strings. The shared shape stays within the existing strict-schema
subset; no arbitrary JSON schema, provider tools or validator relaxation is added.
The companion OOS decoder enforces intent, exclusive payload kind, admitted
fields, readonly state and field limits before reporting success. Normal answers
carry answer/clarify with no edits. The unchanged Console guard still rejects
invalid geometry/identities and stale or foreign-view transactions atomically.

The operator included the same-format repair across the existing shared draft
advisors in this batch. Agent Console's schema serves Proposal, Prototype
promotion, Execution, blocker justifications and Orchestration drafting as well
as ordinary chat. Tests exercise each role through OOS and reject nested-text
fallback against both actual provider schemas. Existing structured Refinement,
source-editor and source-generation formats retain their separate contracts.

No profile, model selection, effort, credential, egress permission, timeout,
retry, privilege, canonical mutation or admission decision changes. Legacy normal
HTTP answers remain readable through OOS's compatibility serialization.

The operator also included workflow-knowledge/context repair in this batch.
OOS supplies trusted per-role guidance and canonical maturity/source-catalog
facts; Console supplies current workflow observations/checks and explicit missing
evidence. Paired CGG/OOS guards deny shortened editable context before inference.
No shared registry, provider tool or automatic repository-file read is added.
Source references do not claim their contents were loaded. This extends existing
task instructions and context admission without changing Platform input schemas.

## Artifact And Deployment Evidence

- Build workflow run: pending batch publication
- Published image tag/digest: none for this source batch
- Recorded prod revision: none; this is local dev-integration work
- Runtime activation: pending exact paired CGG/OOS/Console source and Security review; land CGG and Platform dependencies before their consumers

## Host Or Runtime Recovery

No host repair is part of this output-contract change. Normal Platform activation
consumes reviewed complete source after operator preview review. Rollback selects
the prior accepted complete source; private saved operator work remains retained.

## Validation

The actual provider schemas pass the existing strict-schema validator. Negative
cases reject missing intent and JSON Patch arrays. Existing gateway/runtime tests
pass with native output; remaining owner/profile and paired runtime checks precede
publication. Source validation alone is not operating acceptance.

## Live Verification

Local strict-schema and gateway behavior checks passed. This uncommitted batch
has no new live-provider or exact-source commissioning evidence yet. Existing
accepted live source remains unchanged; provider latency and unknown completion
are distinct from the edit grammar repaired here.

## Follow-Up

- Owner: Platform/OOS/Console with Security retaining acceptance authority.
- Required follow-up: operator preview review, complete owner checks, exact composed source acceptance and normal activation proof.
- Closure condition: reviewed batch qualified through its existing runtime and cleanup paths; no source-only proof substituted for live readiness.
