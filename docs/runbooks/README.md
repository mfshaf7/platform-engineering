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
checks, it should live under that product directory instead of growing the
shared platform runbooks tree.

Target location:

- `products/<product>/`

## Current Reality

Some OpenClaw-specific release runbooks still live here because OpenClaw was the
first product to drive the platform automation.

Treat those as incumbent paths to rationalize over time, not as the model for
future products.
