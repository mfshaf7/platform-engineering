# Governance Operations Console Platform Integration

This directory defines how the Platform supplies display-safe operator
identity and session truth to the Governance Operations Console server.

## Current Shape

The current implementation extends the existing `dev-integration` session
manifest. Platform maps one admitted local operator to reviewed roles and named
authority, then publishes a private non-secret projection for the Console
server. The browser must receive only that bounded projection.

This is a real local session source within the single-operator
`dev-integration` trust boundary. It is not federated identity, stage evidence,
production authentication, or permission for the Console to mutate an owning
system directly.

## Ownership

- Platform issues and revokes the projection.
- Console source consumes it and fails closed.
- OOS authorizes workflow commands and records attribution.
- Security Architecture approves activation of the combined boundary.

Primary operator procedure:

- [Manage the Console session projection](runbooks/manage-session-projection.md)

Machine-readable policy:

- [session-projection-policy.yaml](session-projection-policy.yaml)
