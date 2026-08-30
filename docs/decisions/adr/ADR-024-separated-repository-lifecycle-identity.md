# ADR-024: Separated Repository Lifecycle Identity

## Status

- Accepted for bounded dev-integration evidence

## Context

Repository archive and unarchive are provider mutations. The existing custody
identity is intentionally read-only, while the provisioning identity is scoped
to an organization and repository creation. Broadening either identity would
couple unrelated duties and make revocation unnecessarily disruptive.

## Decision

Use a third GitHub App installation dedicated to repository lifecycle changes.
Each issued token targets exactly one repository and carries only
`Administration: write` plus GitHub's implicit `Metadata: read`. The request
binds both the repository's `owner/name` coordinate and immutable provider id;
token readback must prove the same repository before delivery.

Platform keeps the private key in a separate Vault path and projects only a
short-lived installation token through a distinct Kubernetes Secret and OOS
environment variable. Provider traffic is pinned to `https://api.github.com`
and redirects are denied. Loopback HTTP is available only for explicit sandbox
evidence.

Normal lifecycle workflow activation remains disabled. This decision supplies
the bounded identity and projection boundary needed by the later Security, OOS,
Console, and composed-evidence children under Feature `#915`.

## Consequences

- Archive and unarchive authority can be delivered and revoked independently.
- Custody observation and repository provisioning retain their narrower
  permissions.
- Receipts identify the exact repository, App, installation, permissions,
  contract digest, token expiry, and value-free binding digest without storing
  credentials.
- Rollback revokes the token and removes its projection without changing the
  repository's current provider state.
- Hard deletion, provider ownership transfer, personal credentials, and ambient
  `gh` authentication remain outside this boundary.

## Alternatives Considered

- Broaden the read-only custody identity: rejected because observation must not
  gain mutation authority.
- Reuse the provisioning identity: rejected because organization-wide creation
  authority is broader than one-repository lifecycle mutation.
- Use an operator credential: rejected because durable workflow authority must
  not depend on a personal identity.
