# Runbooks

This directory is for shared platform runbooks.

Examples:

- bootstrap
- Vault
- Argo
- host-stack provisioning
- platform-wide rollback and incident process

## Product-Specific Rule

If a runbook is specific to one product’s runtime, release flow, or visibility
checks, it must live under that product directory instead of growing the shared
platform runbooks tree.

Target location:

- `products/<product>/runbooks/`

## Start Here For Operator Access

The shared platform entrypoint docs are:

- [../components/README.md](../components/README.md)
- [../workflows/README.md](../workflows/README.md)
- [dev-integration-profiles.md](dev-integration-profiles.md)
- [assess-environment-readiness.md](assess-environment-readiness.md)
- [full-platform-runtime-drill.md](full-platform-runtime-drill.md)
- [access-platform-uis.md](access-platform-uis.md)
- [access-grafana.md](access-grafana.md)

Then use the product-local access runbooks:

- `products/openclaw/runbooks/access-openclaw.md`
- `products/openproject/runbooks/access-openproject.md`

## Legacy Runbooks

Historical or retired platform migration material lives under `legacy/`.

That directory is not part of the current operator surface. Use it only when
you intentionally need historical Docker-to-Platform-Core migration context.
