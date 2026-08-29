# Repository Provider Identity

## Purpose

This is the primary Platform operator surface for the machine identity used by
the existing-repository custody workflow. It delivers provider credentials to
OOS but does not authorize custody, choose repositories, or mutate Workspace
Intake, active inventory, Delivery Catalog, or product state.

The source contract is
[`security/repository-provider-identity.yaml`](../../../security/repository-provider-identity.yaml).
The operator command is `make repository-provider-identity`.

## Required GitHub App Shape

Create one dedicated GitHub App for repository-custody readback:

- no user authorization
- no webhook
- no event subscriptions
- repository permission `Metadata: read` only
- installation restricted to selected repositories
- no organization, account, administration, contents, issues, pull-request,
  workflow, package, or write permission

Install it only on the explicitly approved repository set. Keep its private key
under the Platform Vault path recorded in the source contract. App and
installation ids are non-secret runtime inputs; the private key and every
issued token are secret values.

The accepted security decision is
[Repository Custody Provider Identity Boundary Review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-29-repository-custody-provider-identity-boundary.md).

## Validate Source Contract

```bash
make repository-provider-identity ACTION=validate
```

## Materialize The Private Key

Use an operator-private temporary file. Do not print the value or pass it in a
command argument.

```bash
umask 077
PRIVATE_KEY_FILE="$(mktemp)"
k3s kubectl -n vault exec vault-0 -- env \
  VAULT_ADDR=http://127.0.0.1:8200 \
  VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv get -field=privateKey \
  kv/components/operator-orchestration-service/dev-integration/repository-provider \
  >"$PRIVATE_KEY_FILE"
```

Remove that file as soon as `commission` or `deliver` returns.

## Commission

Commissioning proves the exact App, installation, permission, destination, and
repository scope. The proof token is revoked before the command returns.

```bash
make repository-provider-identity ACTION=commission ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --private-key-file $PRIVATE_KEY_FILE \
  --repository <owner/name> \
  --receipt <operator-private-receipt.json>"
```

Repeat `--repository` for a bounded set. One token request cannot span GitHub
owners. The receipt contains no private key or installation-token value.

## Deliver To Dev Integration

Delivery mints a new token with the same exact scope and projects it into the
runner-owned `accepted-idea-delivery` namespace as
`operator-orchestration-service-repository-provider`. The token expires within
one hour. Rerun delivery to rotate it during an active local session.

The command resolves the namespace from an operator-owned `0600`
`current-session.yaml`, revalidates the active profile against the Workspace
Governance registry and owner profile, and denies any Kubernetes API endpoint
that is not loopback-local. A caller cannot supply an arbitrary namespace.

```bash
make repository-provider-identity ACTION=deliver ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --private-key-file $PRIVATE_KEY_FILE \
  --repository <owner/name> \
  --session-manifest <workspace-root>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace-root> \
  --kubectl 'k3s kubectl' \
  --receipt <operator-private-delivery-receipt.json>"
```

The Console/OOS composition owns consuming this Secret. Delivery alone does
not enable the source runtime gate or claim an end-to-end custody result.

## Revoke

Revocation invalidates the issued installation token and removes its
Kubernetes projection. It does not delete, archive, transfer, or change any
repository.

```bash
make repository-provider-identity ACTION=revoke ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --repository <owner/name> \
  --session-manifest <workspace-root>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace-root> \
  --receipt <operator-private-revocation-receipt.json>"
```

If the installation itself is compromised, suspend or uninstall the GitHub App
installation and rotate the private key before any new delivery. The normal
runtime must remain disabled while the identity is unavailable or mismatched.

## Evidence

Retain only:

- exact source revision and contract digest
- app and installation ids
- repository names and immutable provider repository ids
- exact permission readback
- credential-binding digest
- issue and expiry timestamps
- commission, delivery, or revocation outcome

Never retain the private key, app JWT, or installation token in source, logs,
receipts, Review Packets, or browser responses.
