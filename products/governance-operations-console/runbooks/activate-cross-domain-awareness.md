# Activate Cross-Domain Awareness

This procedure activates the Governance Operations Console against the exact
Security-approved OOS and WGCF sources in local `dev-integration`. It installs
one dedicated read-only WGCF history credential, launches owner tunnels and the
Console as persistent user services, and records secret-free receipts.

## Preconditions

- the approved source revisions in `cross-domain-activation-policy.yaml` are checked out cleanly
- the `accepted-idea-delivery` and `governance-control-fabric` profiles are active from those revisions
- the Console dependencies are installed
- Security review exists at the pinned Security revision

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

## Rollback Boundary

`rollback` stops and disables only the three Console activation services and
removes the dedicated WGCF history-reader binding. It preserves OOS and WGCF
owner data, profile state, databases, evidence stores, and unrelated runtimes.

`cleanup` additionally removes generated unit files and local private runtime
files while preserving receipts.

This procedure proves local `dev-integration` operation only. It does not claim
stage readiness, production readiness, deployment approval, or broader
Security authority.
