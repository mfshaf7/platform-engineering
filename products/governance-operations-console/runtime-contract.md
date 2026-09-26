# Runtime Contract

## Scope

Platform projects `console-operator-identity/v1` from an active local
`dev-integration` session. The projection is a server-side read model, not an
authentication credential.

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

## Limits

The local operating-system account remains inside the `dev-integration` trust
boundary. This implementation does not claim federated login, MFA, remote
revocation, stage readiness, production readiness, or Security acceptance.

Console route enforcement and OOS workflow authorization remain separate
controls. A valid projection alone grants no domain mutation authority.
