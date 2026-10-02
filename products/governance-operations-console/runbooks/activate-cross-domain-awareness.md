# Activate Cross-Domain Awareness

This procedure activates the Governance Operations Console against the exact
Security-approved OOS and WGCF sources in local `dev-integration`. It installs
one dedicated read-only WGCF history credential, launches owner tunnels and the
Console as persistent user services, and records secret-free receipts.

The activation policy binds the current durable architecture packet, its exact
predecessor, the supersession relationship, Security gate, and approved owner
revisions. A different packet, revision, or Security review fails closed.
That binding selects the reviewed Console read boundary only. It does not prove
Workspace Intake or Inventory configuration, identity projection, direct owner
routes, or operating readiness.

## Preconditions

- the approved source revisions in `cross-domain-activation-policy.yaml` are checked out cleanly
- the `accepted-idea-delivery` and `governance-control-fabric` profiles are active from those revisions
- the Console dependencies are installed
- Security review exists at the pinned Security revision

If a primary checkout contains preserved unrelated local state, select a clean
exact-revision worktree explicitly instead of moving or deleting that state:

```bash
make governance-console-cross-domain ACTION=validate ARGS="\
  --repo-path workspace-governance=<clean-exact-revision-worktree>"
```

The same `ARGS` value must be supplied to each commissioning command. Source
overrides affect only revision validation and process launch; receipts continue
to name canonical repository identities and exact revisions. The executing
Platform checkout must also be clean; every receipt records its exact commit.

Validate without changing runtime state:

```bash
make governance-console-cross-domain ACTION=validate
```

## Rehearsal

```bash
make governance-console-cross-domain ACTION=activate
make governance-console-cross-domain ACTION=status
make governance-console-cross-domain ACTION=restart
make governance-console-cross-domain ACTION=rehearse
make governance-console-cross-domain ACTION=rollback
make governance-console-cross-domain ACTION=cleanup
make governance-console-cross-domain ACTION=activate
make governance-console-cross-domain ACTION=status
```

`status` succeeds only when the Console API reports live, current or partial
owner-backed activity from both OOS and WGCF and contains no fixture authority.
`rehearse` temporarily disconnects the WGCF tunnel, proves that the configured
owner becomes explicitly unavailable without fixture fallback, restores the
tunnel, and proves both owners are live again.
Receipts are retained under
`~/.local/state/platform-engineering/governance-console-cross-domain/receipts/`
without credentials.

These receipts are evidence only for Console-to-owner activity/history reads,
visible owner unavailability, restart, and the Console read-boundary rollback.
They must not be cited as Workspace Intake or Inventory commissioning evidence.
Use the Platform-owned Workspace operations identity `status` action after its
refreshed Security gate is approved.

## Rollback Boundary

`rollback` stops and disables only the three Console activation services and
removes the dedicated WGCF history-reader binding. It preserves OOS and WGCF
owner data, profile state, databases, evidence stores, and unrelated runtimes.

`cleanup` additionally removes generated unit files and local private runtime
files while preserving receipts.

Every rollback or cleanup removes the dedicated WGCF binding and the Console
private environment. It does not revoke or destroy owner-profile sessions,
databases, source history, architecture artifacts, Review Packets, denied-path
evidence, or Security decisions.

This procedure proves local `dev-integration` operation only. It does not claim
stage readiness, production readiness, deployment approval, or broader
Security authority.
