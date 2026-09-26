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
