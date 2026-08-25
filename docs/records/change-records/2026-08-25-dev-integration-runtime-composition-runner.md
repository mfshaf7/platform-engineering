# Dev-Integration Runtime Composition Runner

## Summary

- Date: 2026-08-25
- Short title: Shared dependency and credential composition execution
- Environment: local `dev-integration`
- Severity: Medium

## Classification

- Type: shared platform runtime control
- User-facing impact: Operators can start, inspect, and stop the registered
  Work Design runtime composition through the existing dev-integration command
  family without manually coordinating three profiles or handling a shared
  caller credential.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `workspace-governance`, `operator-orchestration-service`,
  `context-governance-gateway`, `security-architecture`
- Related architecture: Workspace Delivery ART #884 architecture packet v12
- Related ADR: Not required; this extends the approved dev-integration runner
  and workspace composition contract.

## Root Cause

- Immediate failure: The Console Work Design path depended on active OOS, CGG,
  and governed AI gateway profiles, but the shared runner could operate only
  one profile at a time.
- Actual root cause: Runtime dependency ordering, cross-namespace endpoint
  projection, and local caller-credential custody existed as architecture and
  contract truth but had no executable Platform control.
- Why it escaped earlier controls: Feature-level end-to-end cases were not
  bound to an executable child Landing Unit before the original children
  closed.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #1000 records the merged commit.
- Guardrails added:
  - mutually exclusive profile and composition selectors
  - active participant and Platform runtime-owner checks
  - cycle and projection validation
  - provider-first start and consumer-first teardown
  - operator-private runtime-generated credential custody
  - profile-bounded environment projection with no secret values in arguments,
    manifests, or status output
  - redacted composition state, repeatable `up`, bounded rollback, and failed
    status or teardown projection

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #1000 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: Not applicable; this work adds local runner capability and does
  not activate a governed runtime.
- Functional verification:
  - `python3 scripts/test_dev_integration_compositions.py`
  - `python3 scripts/test_dev_integration.py`
  - `python3 scripts/test_dev_integration_host_services.py`
  - `python3 scripts/validate_repo_structure.py`
  - `python3 scripts/validate_operational_docs.py`
- Residual risk: CGG and OOS profile scripts do not consume the new projections
  until ART #1001 and #1002 land; Security acceptance remains ART #1003.

## Follow-Up Actions

- Required follow-up: ART #1001 projects the caller binding into CGG.
- Required follow-up: ART #1002 projects dependency endpoints and caller
  identity into OOS and proves the composed Work Design path.
- Required follow-up: ART #1003 reviews the exact composed trust boundary.
- Owner: Platform Engineering, CGG, OOS, and Security Architecture according to
  their existing boundaries.
