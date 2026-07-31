# Temporal Access

## Current Operator Path

There is no Temporal runtime or UI to access.

After the workspace registry records the proposed profile, operators may
inspect its non-launchable status:

```bash
make devint-status PROFILE=temporal
```

The following remain denied until the profile is `active` and its owner scripts
implement the admitted runtime:

```bash
make devint-up PROFILE=temporal
make devint-access PROFILE=temporal
make devint-smoke PROFILE=temporal
```

## Future Diagnostic Access

If admitted, `make devint-access PROFILE=temporal` will be the primary local
diagnostic path. A Temporal UI may expose workflow history and runtime
diagnostics, but it is not the business command surface.

Operators control workflows through OOS. Governance Operations Console also
calls OOS and never receives direct Temporal credentials.

## Credentials

No Temporal credentials or secrets are approved yet.

Build admission must define:

- OOS client and worker identity
- activity-worker identity boundaries
- namespace and task-queue authorization
- local secret generation or delivery
- credential rotation and revocation
- denial of direct Console access

Do not create or distribute credentials from this proposed contract.
