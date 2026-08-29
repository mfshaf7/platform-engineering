# Repository Provisioning Identity

## Purpose

This is the Platform operator surface for the GitHub App identity that creates
new repositories after WGCF and OOS approve one exact request. It is separate
from the read-only existing-repository identity.

The source contract is
[`security/repository-provisioning-identity.yaml`](../../../security/repository-provisioning-identity.yaml).
The operator command is `make repository-provisioning-identity`.

## Required GitHub App Shape

Create a dedicated GitHub App owned by the admitted organization:

- no user authorization, webhook, or event subscriptions
- repository permission `Administration: write`
- repository permission `Contents: read`
- implicit repository permission `Metadata: read`
- no organization-management, issues, pull-request, workflow, package, or
  unrelated permission
- installation on the exact target organization only

The private key lives at
`kv/components/operator-orchestration-service/dev-integration/repository-provisioning-provider`.
App and installation ids are non-secret; the private key, App JWT, and issued
tokens are secret.

## Validate

```bash
make repository-provisioning-identity ACTION=validate
```

## Commission

Materialize the Vault `privateKey` property into an operator-private `0600`
temporary file, then run:

```bash
make repository-provisioning-identity ACTION=commission ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --organization <organization> \
  --private-key-file <private-key-file> \
  --receipt <operator-private-receipt.json>"
```

Commissioning verifies the exact organization, App, installation, permission
set, provider destination, and short token lifetime, then revokes the proof
token before recording success.

## Deliver And Revoke

Delivery targets only the runner-owned active `accepted-idea-delivery`
dev-integration session:

```bash
make repository-provisioning-identity ACTION=deliver ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --organization <organization> \
  --private-key-file <private-key-file> \
  --session-manifest <workspace-root>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace-root> \
  --receipt <operator-private-delivery-receipt.json>"
```

The token is projected as
`operator-orchestration-service-repository-provisioning-provider` and expires
within one hour. Revoke it and remove the projection with the same identity,
organization, session, and workspace arguments using `ACTION=revoke`. Revoke
does not delete a repository.

Normal provisioning remains disabled until ART `#1049` proves the composed
Console path. Sandbox evidence cannot substitute for commissioning the real
organization installation.
