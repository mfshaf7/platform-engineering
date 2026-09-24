# Lifecycle Context Composition

This Platform-owned controller commissions the reviewed OOS-to-CGG lifecycle
context boundary in local `dev-integration`. It reuses the admitted
`accepted-idea-delivery` and `context-governance-gateway` profiles and changes
only their lifecycle-specific runtime binding.

Use the bounded operator surface:

```bash
make lifecycle-context ACTION=validate
make lifecycle-context ACTION=up
make lifecycle-context ACTION=status
make lifecycle-context ACTION=smoke ARGS="--work-item-id 1167"
make lifecycle-context ACTION=suspend
make lifecycle-context ACTION=down
make lifecycle-context ACTION=rollback
```

`up` creates or rotates one ephemeral caller secret, projects it only to the
CGG API and OOS broker, and records only its digest. `smoke` proves packet,
denial, explicit raw fallback, replay, restart, and gateway-loss behavior.
Each smoke execution uses a new non-secret proof-run identifier so a partial
or repeated proof cannot collide with an earlier immutable replay key.
Suspension, teardown, and rollback remove only the lifecycle binding and keep
the two profile runtimes, ART, Git, work-session state, CGG custody, and other
CGG routes intact.

This composition has no stage, production, release, model, approval, or
lifecycle-mutation authority. The Console remains an OOS client and receives
neither a CGG route nor the lifecycle credential.
