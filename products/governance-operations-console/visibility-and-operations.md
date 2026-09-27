# Visibility And Operations

Use the product-qualified command:

```bash
make governance-console-session ACTION=inspect \
  ARGS="--projection <operator-private-projection.json>"
```

The inspection result reports only:

- projection status
- principal reference
- session reference and expiry
- source authority, profile binding, and policy digest through the receipt

It does not print credentials because the projection contains none.

Health for this boundary means the projection validates, is current, belongs
to an admitted profile/session, and remains readable only by its owner. Missing
or expired projection is an unavailable identity state, not a fallback to
synthetic authorization.

See [the operator runbook](runbooks/manage-session-projection.md) for issue and
revocation commands.

Project the current admitted workload observations with:

```bash
make governance-console-runtime ACTION=project ARGS="\
  --output <operator-private-runtime-observations.json> \
  --receipt <operator-private-receipt.json>"
```

Inspect freshness and aggregate state without printing workload payloads:

```bash
make governance-console-runtime ACTION=inspect ARGS="\
  --projection <operator-private-runtime-observations.json>"
```

The projection reports Kubernetes workload readiness only. It does not replace
owner health endpoints, OOS readback, WSL resource telemetry, or Security
activation. See [the runtime observation runbook](runbooks/project-runtime-observations.md).
