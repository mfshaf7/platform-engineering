# ADR-006: Retire `openclaw-isolated-deployment` As An Active Architecture Owner

## Status

Accepted

## Context

`openclaw-isolated-deployment` originally carried a mix of reference
architecture, local build seams, copied source trees, and deployment guidance.

That model no longer fits the current platform:

- governed runtime composition is owned by `openclaw-runtime-distribution`
- platform-side OpenClaw operating guidance is owned by
  `platform-engineering/products/openclaw`
- security rationale and trust-boundary judgment are owned by
  `security-architecture`

Leaving `openclaw-isolated-deployment` as an active reference owner would keep
the same truth spread across several repos and recreate drift.

## Decision

Retire `openclaw-isolated-deployment` as an active architecture owner.

Going forward:

- `platform-engineering/products/openclaw`
  - owns the platform-side OpenClaw architecture, owner model, and operator
    workflow
- `security-architecture`
  - owns the security rationale, trust-boundary view, and product security
    overlay for OpenClaw
- `openclaw-runtime-distribution`
  - owns the active stage/prod runtime composition path
- `openclaw-isolated-deployment`
  - remains only as a retirement stub until archival and must not be used for
    active routing

## Consequences

### Positive

- one current landing zone for OpenClaw platform architecture
- one current landing zone for OpenClaw security architecture
- less cross-repo drift and less routing ambiguity
- workspace validators can stop treating the retired repo as active

### Negative

- historical links to the retired repo need cleanup in active docs
- operators must learn the new split between platform product docs and security
  architecture docs

## Supersession

This ADR partially supersedes ADR-001 for the retired
`openclaw-isolated-deployment` reference-architecture role.
