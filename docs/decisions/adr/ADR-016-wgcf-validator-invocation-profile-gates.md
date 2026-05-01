# ADR-016: WGCF Validator Invocation Profile Gates

## Status

- Accepted

## Context

`workspace-governance-control-fabric` is being introduced as a shared runtime
that can plan, invoke, cache, and receipt governance validators. Without a
platform-level decision, teams could treat WGCF as a generic validator runner
and replace direct validator paths before profile gates, receipt custody,
security review, or rollback evidence exist.

The current owner split is deliberate:

- `workspace-governance` owns validator catalog truth and shadow-parity
  contracts.
- `workspace-governance-control-fabric` owns implementation.
- `operator-orchestration-service` remains the Delivery ART mutation
  authority.
- `security-architecture` owns trust-boundary review and acceptance posture.
- `platform-engineering` owns runtime lane admission, deployment posture,
  persistence, observability, and promotion gates.

The platform therefore needs an authoritative gate model before WGCF validator
invocation can become a normal operator or CI path.

## Decision

WGCF validator invocation is admitted through four platform profile gates:

1. `devint-shadow`
   - local-source or local-k3s shadow comparison between direct validators and
     WGCF receipts
   - no stage/prod claims
   - no authority mutation
2. `stage-readiness`
   - governed rehearsal only after platform release-candidate, identity,
     secret-delivery, migration/rollback, security review, observability, and
     backup/restore gates are defined
   - no production use
3. `prod-readiness`
   - normal production invocation only after clean stage evidence, approved
     source or image pin, support-readiness, retention, restore, and
     rollback/suspension evidence exist
   - no break-glass behavior as default operation
4. `break-glass`
   - explicit operator-approved diagnostic invocation with reason, scope,
     expiry, caller identity, direct rollback, receipt, and ledger evidence
   - never a silent default plan

The operational gate surface is:

- `docs/components/workspace-governance-control-fabric/validator-invocation-gates.md`

Default custody posture:

- compact receipts are allowed when bounded, redacted, and reference-based
- raw artifacts are denied by default outside local custody
- redacted or raw artifact custody requires approved retention, access,
  deletion, and restore controls before governed use

Default cutover posture:

- direct validators remain compatibility entrypoints during shadow parity
- WGCF receipts can become normal evidence only after platform gates, current
  security review, receipt parity, and direct rollback exist
- direct validator retirement requires the workspace shadow-parity contract to
  mark a scope retirement-eligible

Observability posture:

- Prometheus remains the current platform metrics and health surface
- OpenTelemetry-compatible correlation may be added later for traces and
  receipt-to-operator linkage
- OpenTelemetry does not replace the existing platform observability model
- logs must not emit raw validator output, secrets, environment dumps, or full
  artifacts

## Consequences

What becomes safer:

- WGCF cannot become a hidden authority path just because it can invoke checks.
- Platform, security, workspace, and ART owner boundaries stay explicit.
- Raw artifact custody is blocked until storage and retention controls exist.
- Direct rollback remains available while shadow parity is proven.

What becomes stricter:

- Shared validator cutover now needs a named platform profile gate.
- Security review must stay current before broad cutover.
- Direct validator removal cannot be bundled into runtime deployment.
- Break-glass execution needs explicit operator evidence.

No platform change record is required for this ADR by itself because it does
not deploy or mutate governed runtime state. Any future stage/prod admission,
runtime storage activation, raw artifact custody activation, or live
environment change must capture the applicable governed change record when it
lands.

## Alternatives Considered

- Let `workspace-governance` alone define cutover.
  - Rejected because runtime lane, persistence, observability, backup, and
    deployment gates are platform-owned.
- Let WGCF replace direct validators after local tests pass.
  - Rejected because local success does not prove artifact custody, caller
    identity, rollback, or security acceptance.
- Treat WGCF as a generic CI runner.
  - Rejected because WGCF is a governance control fabric with receipt and
    admission semantics, not an unbounded execution substrate.
