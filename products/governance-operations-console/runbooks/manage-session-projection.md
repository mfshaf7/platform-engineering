# Manage The Console Session Projection

This is the primary Platform operator surface for the Console's local
identity/session source.

## Validate

```bash
make governance-console-session ACTION=validate
```

## Issue

Run `devint-up` first so the selected active profile has a current manifest.
Then issue the projection from that exact session:

```bash
make governance-console-session ACTION=issue ARGS="\
  --session-manifest <workspace>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --projection <operator-private-runtime>/operator-identity.json \
  --receipt <operator-private-runtime>/operator-identity.receipt.json"
```

The command verifies file ownership, permissions, operating-system identity,
profile admission, lifecycle, timestamps, and policy mapping before publishing.
Reissuing the same session is deterministic. A different active session is
rejected until the old projection is revoked.

## Inspect

```bash
make governance-console-session ACTION=inspect ARGS="\
  --projection <operator-private-runtime>/operator-identity.json"
```

## Revoke

```bash
make governance-console-session ACTION=revoke ARGS="\
  --projection <operator-private-runtime>/operator-identity.json \
  --receipt <operator-private-runtime>/operator-identity-revocation.receipt.json"
```

Revocation publishes an explicit unavailable projection. It does not fabricate
sign-out at an external identity provider. Stop or reset the owning
dev-integration runtime separately when that runtime must also end.

## Failure Handling

Do not widen file permissions, edit a generated projection, or bypass an
operator/profile mismatch. Refresh the owning `dev-integration` session and
issue again. If policy or trust boundaries must change, update the reviewed
source contract and route the security decision separately.
