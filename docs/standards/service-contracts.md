# Service Contracts

## Purpose

This standard defines the minimum visibility and operating contract for any
managed service, plugin, or bridge-facing integration that participates in the
platform.

The point is not to create perfect documentation. The point is to make every
important runtime answerable under incident pressure.

## Minimum Contract

Each managed service should document:

- owner repository
- purpose and trust-boundary role
- health endpoint or health-check method
- logs or diagnostics surface
- metrics or observability surface, if any
- version or attestation mechanism
- required environment variables
- required secrets and where they come from
- expected restart behavior
- expected recovery behavior
- at least one real functional verification step

## Visibility Requirements

At minimum, an operator should be able to answer:

- is the service up
- what configuration it is running with
- what version or commit it is serving
- where its logs are
- where its audit trail is, if it performs privileged or sensitive work
- what downstream component depends on it

## Audit Requirements

For services that cross a privileged boundary, the contract should also name:

- the audit location
- the approval model or permission class
- the attestation or policy-alignment mechanism
- the expected evidence after a repair or rollout

Examples include:

- `openclaw-host-bridge`
- recovery services
- Telegram-initiated host-control delivery paths
- any service that can widen identity, secret access, or host influence

## Runtime Behavior Requirements

The contract should explain:

- what “healthy” means
- what “ready for real use” means
- which behaviors must be checked beyond `/healthz`
- whether the service is always on, on-demand, or environment-scoped

If a service is intentionally environment-scoped, document that explicitly.

## Documentation Rule

When a service contract changes, update both:

- the repo that owns the service implementation
- the platform or security docs that govern how it is used

Changing the live operating model without updating the documented service
contract is a control failure.
