# Repository Lifecycle Identity

## Purpose

This is the Platform operator surface for the GitHub App identity used by the
future governed repository archive and unarchive workflow. It is separate from
read-only custody discovery and organization-wide repository provisioning.

The source contract is
[`security/repository-lifecycle-identity.yaml`](../../../security/repository-lifecycle-identity.yaml).
The operator command is `make repository-lifecycle-identity`.

## Required GitHub App Shape

Create a dedicated GitHub App owned by the admitted organization:

- no user authorization, webhook, or event subscriptions
- repository permission `Administration: write`
- implicit repository permission `Metadata: read`
- no contents, issues, pull-request, workflow, package, organization-management,
  or unrelated permission
- installation available to the exact repository selected for each delivery

The private key lives at
`kv/components/operator-orchestration-service/dev-integration/repository-lifecycle-provider`.
App, installation, and repository ids are non-secret. The private key, App JWT,
and installation tokens are secret.

## Validate

```bash
make repository-lifecycle-identity ACTION=validate
```

## Commission

Materialize the Vault `privateKey` property into an operator-private `0600`
temporary file, then run:

```bash
make repository-lifecycle-identity ACTION=commission ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --organization <organization> \
  --repository <owner/name> \
  --repository-id <immutable-provider-id> \
  --private-key-file <private-key-file> \
  --receipt <operator-private-receipt.json>"
```

Commissioning proves the App owner, installation, exact permission set,
single-repository token scope, immutable repository identity, provider
destination, and short token lifetime. It then revokes the proof token.

## Deliver And Revoke

Delivery targets only the runner-owned active `accepted-idea-delivery`
dev-integration session:

```bash
make repository-lifecycle-identity ACTION=deliver ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --organization <organization> \
  --repository <owner/name> \
  --repository-id <immutable-provider-id> \
  --private-key-file <private-key-file> \
  --session-manifest <workspace-root>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace-root> \
  --receipt <operator-private-delivery-receipt.json>"
```

The token is projected as
`operator-orchestration-service-repository-lifecycle-provider` and expires
within one hour. Revoke it and remove the projection with the same identity,
repository, session, and workspace arguments using `ACTION=revoke`.

This surface does not archive or unarchive a repository. Normal mutation stays
disabled until the remaining Feature `#915` controls and composed evidence are
accepted.
