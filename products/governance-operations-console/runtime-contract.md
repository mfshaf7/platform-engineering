# Runtime Contract

## Scope

Platform projects `console-operator-identity/v1` from an active local
`dev-integration` session. The projection is a server-side read model, not an
authentication credential.

Platform projects `console-runtime-observations/v1` from the exact admitted
Kubernetes workloads in `runtime-observation-policy.yaml`. It is a short-lived
runtime read model, not proof that an endpoint or workflow succeeded.

## Guarantees

- operator and profile must be admitted by source policy
- manifest must be an operator-owned `0600` regular file
- manifest operator must match the invoking operating-system account
- session start, expiry, source profile, and session identity are explicit
- roles and named authority come only from reviewed policy
- publication is atomic and `0600`
- repeated issue for the same session is deterministic
- a different active session cannot replace the projection without revocation
- stale, expired, malformed, unavailable, or conflicting input fails closed
- receipts contain hashes and references, never secret values
- runtime observations declare source, observation time, expiry, workload
  availability, capability posture, and recovery ownership
- missing workloads and zero ready replicas project unavailable instead of
  becoming synthetic success
- partial readiness projects degraded and collector authority failures stop
  publication
- runtime observations expire after the policy window and must be recollected

## Limits

The local operating-system account remains inside the `dev-integration` trust
boundary. This implementation does not claim federated login, MFA, remote
revocation, stage readiness, production readiness, or Security acceptance.

Console route enforcement and OOS workflow authorization remain separate
controls. A valid projection alone grants no domain mutation authority.

Runtime workload readiness is distinct from WSL host telemetry and from the
Console's configuration capability projection. It grants no workflow,
deployment, release, recovery, or Security authority.

## Cross-Domain Activation

The Platform activation command may compose only the exact reviewed Console,
OOS, and WGCF revisions declared in `cross-domain-activation-policy.yaml`.
Console access to OOS and WGCF is server-only and loopback-bound. The generated
receipt proves source revisions, owner visibility, restart, or rollback without
containing credentials or owner payloads.

Rollback removes only Console-owned user services and the dedicated WGCF
history-reader credential. It must preserve owner databases, workflow state,
evidence stores, profile sessions, and unrelated runtimes.
