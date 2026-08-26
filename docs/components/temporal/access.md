# Temporal Access

## Current Operator Path

Temporal has no public or direct business UI. Operators may inspect the active
source profile even while no composed runtime is present:

```bash
make devint-status PROFILE=temporal
```

The registered composition is the normal launch path after Workspace binding
#1019 and merged-runtime proof #1020 land. This source activation does not claim
that launch has happened:

```bash
make devint-up COMPOSITION=refinement-catalog OPERATOR=<operator>
make devint-access PROFILE=temporal
make devint-smoke PROFILE=temporal
make devint-backup PROFILE=temporal
make devint-restore PROFILE=temporal BACKUP_FILE=<path> CONFIRM=restore-temporal
```

## Diagnostic Access

`make devint-access PROFILE=temporal` is the primary local diagnostic path only
while the composition is running. The Temporal UI may expose workflow history and runtime
diagnostics through an operator-local port-forward only. It is not the business
command surface.

Operators control workflows through OOS. Governance Operations Console also
calls OOS and never receives direct Temporal credentials.

## Credentials

Source now defines separate identities and secret references for:

- OOS client and worker identity
- activity-worker identity boundaries
- namespace and task-queue authorization
- separate operator-local PostgreSQL admin and Temporal application secret
  generation
- credential rotation and revocation
- denial of direct Console access

The profile does not commit secret values. Once the composition is proven,
runtime credentials are generated for its operator-scoped lifetime and removed
during teardown.

The source-reviewed commissioning adapter is not an alternate access path. Its
internal runtime script rejects caller flags and identifiers unless the full
source-controlled Security approval, consumed permit, execution claim, and
exact operator-scope lease revalidate first. Its source is acquired from the
clean permit-bound Platform revision rather than the mutable current checkout.
The complete profile tree is compared byte-for-byte with the exact
commit and may contain no extra files, so Git index flags cannot hide executor
changes. Those verified bytes are sealed in memory and projected by Bubblewrap
as a private read-only profile tree at the expected runtime path. The mutable
checkout path is never used as executable source. One per-authorization lock
serializes initial setup and exact retry.
