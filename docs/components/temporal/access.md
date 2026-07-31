# Temporal Access

## Current Operator Path

There is no Temporal runtime or UI to access.

Operators may inspect the build-admitted, non-launchable status:

```bash
make devint-status PROFILE=temporal
```

The following remain denied until fresh Platform and Security decisions make
the profile `active`:

```bash
make devint-up PROFILE=temporal
make devint-access PROFILE=temporal
make devint-smoke PROFILE=temporal
make devint-backup PROFILE=temporal
make devint-restore PROFILE=temporal BACKUP_FILE=<path> CONFIRM=restore-temporal
```

## Activated Diagnostic Access

Once activated, `make devint-access PROFILE=temporal` is the primary local
diagnostic path. A Temporal UI may expose workflow history and runtime
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

The profile does not commit secret values or create credentials while
build-admitted. Runtime identity behavior still requires operating proof and
fresh Security acceptance before activation.
