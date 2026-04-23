# Shared-Component Observability Overlays

This directory owns the machine-readable catalogs for shared-component
observability overlays.

These overlays sit on top of the shared platform observability baseline without
turning the shared stack into a product-owned surface.

Current admitted shared-component overlays:

- `operator-orchestration-service`
- `openproject`
- `vault`
- `external-secrets`
- `platform-postgresql`
- `host-bridge`

Use these catalogs to answer:

- which shared component overlay is admitted
- which repo owns the overlay
- which local platform assets currently define or expose that overlay
- whether the overlay is active, planned, or still in compatibility shaping

Read these with:

- [../../docs/components/observability/README.md](../../docs/components/observability/README.md)
- [../../docs/components/observability/model.yaml](../../docs/components/observability/model.yaml)
- [../../docs/components/observability/validation-policy.yaml](../../docs/components/observability/validation-policy.yaml)
