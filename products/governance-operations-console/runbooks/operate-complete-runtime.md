# Operate the complete Console runtime

This is the primary Platform operator surface for the complete local
Governance Operations Console runtime. It composes the existing
`refinement-catalog`; it does not create another runtime, workflow engine, or
authority plane.

The Console submits operator intent to OOS. OOS authenticates, persists, and
coordinates the bounded command. The Platform provider exposes only the
finite actions declared in `complete-runtime-policy.yaml` and performs effects
through the existing `dev_integration.py` owner command. Console and browser
processes never receive the Platform provider credential.

## Security gate

Source validation is expected to report `security-pending` before work item
`#1303` lands. Activation remains blocked in that state.

Security owns these two files in `security-architecture`:

- `docs/reviews/components/2026-10-15-governance-console-platform-operation.md`
- `docs/reviews/components/2026-10-15-governance-console-platform-operation.yaml`

The YAML decision must accept gate `gate:platform-operation-security`, work
item `#1303`, the current Architecture Packet reference, the exact reviewed
revisions for Console, OOS, Platform, Workspace Governance, and WGCF, and the
exact reviewed Platform tree. The Markdown review must contain those same
bindings. Runtime reads the decision from current clean Security `origin/main`
and materializes private policies; no post-review Platform source-pin edit is
required.

## Commands

Validate source without changing runtime:

```bash
make governance-console-complete-runtime ACTION=validate
```

After the exact Security decision and all reviewed owner revisions are on
clean `main`, activate and inspect:

```bash
make governance-console-complete-runtime ACTION=activate
make governance-console-complete-runtime ACTION=status
```

Recover the admitted services and re-prove current readback:

```bash
make governance-console-complete-runtime ACTION=restart
```

Run the bounded operating proof only during work item `#1291` commissioning:

```bash
make governance-console-complete-runtime ACTION=verify-operating
```

That proof checks authenticated startup, invalid-credential denial, revoked
gate denial, stale-marker denial, provider process-loss recovery, full restart,
rollback, teardown, and restoration to normal availability. It retains only
credential-free receipts.

## Stop and cleanup

`rollback` removes Console-facing services and the OOS-to-Platform binding but
preserves the existing composition and owner state. `cleanup` additionally
removes generated credentials and private materialized policy. `teardown`
performs cleanup and suspends the complete composition.

```bash
make governance-console-complete-runtime ACTION=rollback
make governance-console-complete-runtime ACTION=cleanup
make governance-console-complete-runtime ACTION=teardown
```

Rollback and teardown never delete ART, Git, OOS workflow, WGCF, Security, or
owner evidence.

## Failure interpretation

- `Security decision ... unavailable`: `#1303` has not landed at the declared
  path, or Security `main` is not current and clean.
- `missing, stale, revoked, or outside scope`: the decision does not accept
  this exact gate, initiative, work item, or Architecture Packet.
- `not the exact Security-reviewed source`: one owner checkout differs from
  the accepted revision, or the Platform tree differs from the reviewed tree.
- `active runtime does not match`: run `restart` or `activate`; do not edit the
  private policy.
- provider or Console readback unavailable: inspect the named systemd service
  and owner workload, repair the dependency, then run `restart`.

Private state and receipts live below
`~/.local/state/platform-engineering/governance-console-complete-runtime/`.
Do not paste its private files into chat, ART, logs, or source control.
