# ADR-022: Bounded Repository Provider Identity

## Status

- Accepted

## Context

The repository-custody workflow must verify existing GitHub repositories
without using an operator browser session, a personal access token, or broad
repository permissions. OOS owns workflow authorization, while Platform owns
machine-identity custody and runtime projection. The first consumer is the
local `accepted-idea-delivery` dev-integration profile; stage and production
activation are not approved.

Repository names are mutable. Evidence and runtime revocation therefore need
the provider's immutable numeric repository identity as well as the readable
owner/name value. Runtime delivery must also prove that its Kubernetes target
is the active local dev-integration session rather than trusting a caller
supplied namespace or context.

## Decision

Use one dedicated GitHub App installation for repository-custody readback with:

- `Metadata: read` as its only repository permission
- no user authorization, webhook, or event subscription
- selected-repository installation scope
- explicit repository scope on every short-lived installation token
- private-key custody in Platform Vault
- no private key, app JWT, or installation token in source or evidence

Platform commissions the identity by verifying the exact App, installation,
permissions, selected repositories, provider destination, and immutable
repository ids, then revokes the proof token before recording success.

Runtime delivery remains limited to the registered active
`accepted-idea-delivery` profile. The operator command derives its namespace
from the runner-owned current-session manifest, revalidates the profile against
Workspace Governance and owner-repo source, and requires a loopback Kubernetes
API through the Platform-owned `k3s kubectl` command. The projected Secret
binds the verified provider repository identities to
the exact dev-integration profile and session. Revocation validates that
binding before revoking the token or deleting the Secret.

Normal runtime activation remains disabled until the OOS and Console
composition work is accepted. OOS continues to own custody workflow
authorization and repository choice; Platform identity delivery does not
mutate Workspace Intake, Delivery Catalog, repository state, or product state.

## Consequences

- Repository verification uses least privilege and remains independent of an
  operator's GitHub session.
- Receipts survive repository rename or name reuse because immutable provider
  ids are bound into the evidence.
- An arbitrary namespace or remote Kubernetes context cannot receive the
  credential through the supported operator command.
- Runtime delivery depends on a current admitted dev-integration session and
  must fail closed when the profile, manifest, namespace, or cluster differs.
- Compromise requires GitHub App suspension or uninstall, private-key rotation,
  issued-token revocation, and removal of the runtime projection.
- A governed stage or production identity requires a separate security and
  platform decision; this ADR does not authorize one.

The source implementation is governed by the accepted
[Repository Custody Provider Identity Boundary Review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-29-repository-custody-provider-identity-boundary.md).

## Alternatives Considered

- Personal access token:
  - rejected because it binds automation to a human identity and usually
    carries broader, longer-lived authority
- OAuth user authorization:
  - rejected because repository custody verification is a machine workflow,
    not a delegated interactive user action
- Caller-supplied Kubernetes namespace:
  - rejected because it cannot prove the dev-integration lane or prevent
    accidental stage or production projection
- GitHub repository name as the only identity:
  - rejected because names can be renamed and reused
