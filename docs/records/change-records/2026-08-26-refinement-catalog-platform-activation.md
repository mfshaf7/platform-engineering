# Refinement Catalog Platform Activation

## Summary

- Date: 2026-08-26
- Short title: Activate bounded Refinement advice and durable apply in dev-integration
- Environment: local `dev-integration`
- Severity: Medium

## Classification

- Type: platform governance activation
- User-facing impact: Activates the reviewed Platform source contracts required
  by the Refinement and Catalog composition without claiming merged runtime,
  Console integration, direct browser access, paid providers, stage, or
  production.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`, `context-governance-gateway`,
  `workspace-governance-control-fabric`, `workspace-governance`, and
  `security-architecture`
- Related architecture: Workspace Delivery ART #884 architecture packet v22
- Related ADR:
  `docs/decisions/adr/ADR-017-temporal-durable-workflow-runtime.md`

## Root Cause

- Immediate failure: The typed Refinement advisor profile remained inactive
  after the composition, domain contracts, and Security review landed.
- Actual root cause: Foundation work deliberately separated source registration
  from the final Platform-owned activation and live composition proof.
- Why it escaped earlier controls: It did not escape; predecessor Landing Units
  installed fail-closed source pending Security review #1012 and activation
  work item #1013.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #1013 records the merged commit.
- Guardrails added:
  - exact Refinement caller, task, schema, and local model binding activation
  - exact OOS and WGCF namespace-and-identity admission to Temporal frontend
  - positive typed advice and suspended-profile denial before provider access
  - cleanup of both a partially started failing profile and completed dependencies
  - one bounded operator-template source with exactly one sanitized
    `{operator}` token and no general formatting or credential interpolation
  - one profile-namespace source that projects the runner's exact bounded peer
    namespace without profile-local reconstruction
  - default-deny governed-AI gateway ingress with admission only for its smoke
    probe and the exact composition-projected OOS namespace and API workload
  - composition-only OOS business workflow and direct Console access denial
  - current Temporal and governed-AI operator documentation
  - no paid-provider, stage, production, tool, or autonomous mutation expansion

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #1013 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: Not claimed by this source Landing Unit; merged runtime proof is
  owned by ART #1020.
- Source verification:
  - the exact Refinement model and Temporal profiles validate as active
  - the composition admits only the reviewed OOS and WGCF identities
  - operator-template bindings render one sanitized operator identity
  - profile-namespace bindings preserve the runner-computed namespace for long
    operator identities
  - gateway ingress rejects pods outside the isolated probe and composed OOS
    workload boundary before request-level caller policy runs
  - unsupported placeholders, ambient values, and unsafe syntax fail closed
  - failed starts clean up the failing profile and completed dependencies
- Residual risk: ART #1019 must project the operator-scoped namespace and ART
  #1020 must prove the merged runtime before ART #1014 integrates the Console.
  Stage, production, and paid-provider activation remain prohibited.

## Follow-Up Actions

- Required follow-up: ART #1019 aligns the Workspace binding, ART #1020 proves
  the merged composition and teardown, then ART #1014 integrates the Governance
  Operations Console through its same-origin server and OOS only.
- Owner: Governance Operations Console, OOS, Platform Engineering, and Security
  Architecture according to their existing boundaries.
