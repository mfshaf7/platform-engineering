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
- explicit installation scope: selected repositories, or the account metadata
  connection described below
- no organization, account, administration, contents, issues, pull-request,
  workflow, package, or write permission

Approve either the selected repository set or one complete account's metadata
scope explicitly; never fall back from a rejected selection to broader access.
Keep its private key
under the Platform Vault path recorded in the source contract. App and
installation ids are non-secret runtime inputs; the private key and every
issued token are secret values.

The accepted security decision is
[Repository Custody Provider Identity Boundary Review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-29-repository-custody-provider-identity-boundary.md).

The account metadata extension is reviewed separately in
[Account Repository Reader](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-03-account-repository-reader.md).
Source availability alone does not activate the connection or qualify a customer
installation.

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

## Account Metadata Reader

Use this mode when a personal GitHub account or organization should be connected
once, including private repositories created later. It is an explicit
**Metadata: read only** grant over that account. It grants neither source-content
access nor repository creation, settings changes, archive or deletion. Customers
needing selected-repository isolation may retain the original mode, whose access
set must then be maintained deliberately.

The App must still have only Metadata read permission and no events. Install it
on the intended account with **All repositories**. A private App can be installed
only on its owning account; a public App can be installed on other accounts.
Verify the intended installation account before proceeding. Making the App
installable by another account does not make repositories public.

After the exact source review is accepted, materialize its key through the
existing protected Vault procedure above. Use the existing command with
`--account` instead of `--repository`:

```bash
make repository-provider-identity ACTION=commission ARGS="\
  --app-id <app-id> --installation-id <installation-id> \
  --account <account-login> --private-key-file $PRIVATE_KEY_FILE \
  --receipt <operator-private-commission-receipt.json>"

READER_RECEIPT="$HOME/.local/state/platform-engineering/governance-console-complete-runtime/private/repository-reader-delivery.json"
make repository-provider-identity ACTION=deliver ARGS="\
  --app-id <app-id> --installation-id <installation-id> \
  --account <account-login> --private-key-file $PRIVATE_KEY_FILE \
  --session-manifest <workspace-root>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace-root> --kubectl 'k3s kubectl' \
  --receipt $READER_RECEIPT"
```

Remove the temporary key after delivery. Keep the generated receipt private and
unchanged: it is the selection binding for the existing complete-runtime timer.
Absence of that file does not select an App, account or credential. The operator
cannot combine `--account` with a repository list. The producer verifies the
native account/installation and metadata-only App before requesting an
installation token **without a repository filter**. Future repositories under
the approved account therefore do not require another reader setup or token
scope edit. Each request still verifies immutable repository identity, and OOS
rejects another account.

The existing `governance-console-repository-credentials` timer maintains this
optional connection alongside the existing identities. After reviewed source
activation, use `make governance-console-complete-runtime ACTION=refresh-credentials`
to reconcile immediately. Tokens renew when fewer than twenty minutes remain.
The same group rollout consumes the protected Secret and its delivery version;
unchanged healthy ticks do not rotate it or create another service. Missing
projection is restored only from a valid existing selection. A matching prepared
delivery resumes without reissuing a token; malformed or foreign state withholds
the connection. Previous tokens retire only after consumption is proven.

Renewal uses a locked compare-and-swap of the protected selection. If disconnect
or replacement changed that selection, a stale renewal cannot mint/project over
it. Revocation clears the reader's consumer fields through the same group
rollout, preserving the other identities and core operation. Always write a
maintained connection's revoke outcome to its same `$READER_RECEIPT` selection.

Reader Secret references are optional so revocation does not prevent core
startup. A failed reader cannot block renewal of the existing five identities.
Credential-consumption proof is not a provider health check: use an actual
Console lookup to establish current connectivity. Never use the provisioning
token as a reader fallback.

For revocation, run the existing `revoke` action with the same `--account`, App,
installation and session arguments, writing the outcome to `$READER_RECEIPT`.
This revokes the token and removes its projection; it preserves repositories and
workflow history. Reconnection requires the normal reviewed delivery procedure.
The current implementation supports one selected reader account per local
composition. Customer-facing registration and independent-installation
qualification remain product-readiness work.

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
