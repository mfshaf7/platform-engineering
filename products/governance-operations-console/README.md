# Governance Operations Console Platform Integration

This directory defines how the Platform supplies display-safe operator
identity, session truth, and admitted runtime observations to the Governance
Operations Console server.

## Current Shape

The current implementation extends the existing `dev-integration` session
manifest. Platform maps one admitted local operator to reviewed roles and named
authority, then publishes a private non-secret projection for the Console
server. The browser must receive only that bounded projection.

This is a real local session source within the single-operator
`dev-integration` trust boundary. It is not federated identity, stage evidence,
production authentication, or permission for the Console to mutate an owning
system directly.

Platform also observes an explicit policy set of Kubernetes workloads and
publishes a short-lived `console-runtime-observations/v1` projection. Runtime
readiness, freshness, source references, capability posture, and recovery
ownership stay explicit. This projection does not claim endpoint semantics,
workflow success, host telemetry, deployment approval, or Security acceptance.

## Ownership

- Platform issues and revokes the projection.
- Platform collects and expires the runtime observation projection.
- Console source consumes it and fails closed.
- OOS authorizes workflow commands and records attribution.
- Security Architecture approves activation of the combined boundary.

Primary operator procedure:

- [Manage the Console session projection](runbooks/manage-session-projection.md)
- [Project Console runtime observations](runbooks/project-runtime-observations.md)

Machine-readable policy:

- [session-projection-policy.yaml](session-projection-policy.yaml)
- [runtime-observation-policy.yaml](runtime-observation-policy.yaml)
