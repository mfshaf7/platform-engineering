# ADR-023: Separated Repository Provisioning Identity

## Status

- Accepted for bounded dev-integration evidence

## Context

Existing-repository custody uses a selected-repository GitHub App with only
`Metadata: read`. New repository creation needs organization-bound
`Administration: write` and initialized-content readback. Broadening the
existing identity would give a routine read path mutation authority and break
least privilege.

## Decision

Use a second GitHub App installation dedicated to repository provisioning.
The installation must be bound to one exact organization, have exactly
`Administration: write`, `Contents: read`, and GitHub's implicit
`Metadata: read`, and have no user authorization,
webhook, event subscription, or unrelated permission. Platform keeps its
private key in a separate Vault path and delivers only a short-lived
installation token through a distinct Kubernetes Secret and OOS environment
variable.

OOS chooses the read or provisioning token from the immutable custody action.
Normal provider traffic is pinned to `https://api.github.com` and denies
redirects. Loopback HTTP is available only under an explicit sandbox setting.
Receipts contain the organization, App and installation ids, exact permission
set, contract digest, token expiry, and value-free credential-binding digest;
they never contain secret values.

Normal runtime activation remains disabled until Console composition and
positive and negative end-to-end evidence are accepted under ART `#1049`.

## Security Review

Security Architecture review `openproject://work_packages/1047` accepted this
inactive source boundary with findings and requires the dedicated App owner,
installation target, exact permissions, secret delivery, provider destination,
audit, recovery, and revocation controls implemented here. The durable review
is [Repository Provisioning Authority Review](https://github.com/mfshaf7/security-architecture/blob/0bf89e00195bc30c580ccff9bc2f5b3c11902f9a/docs/reviews/components/2026-08-29-repository-provisioning-authority.md).

## Consequences

- Read-only custody never receives repository-creation authority.
- Provisioning authority can be revoked without disabling existing-repository
  readback.
- The provider destination and organization are deterministic and auditable.
- Platform commissioning requires a real organization GitHub App installation;
  a personal-account fallback is prohibited.
- Rollback revokes the issued token, removes its runtime projection, and keeps
  governance evidence without deleting a created repository.

## Alternatives Considered

- Broaden the existing custody App: rejected because readback would inherit
  mutation authority.
- Personal or ambient `gh` credentials: rejected because workflow authority
  must not depend on an operator identity.
- One long-lived installation token: rejected because installation tokens are
  short-lived and revocable runtime material.
