# Scripts

This directory contains a mix of shared platform scripts, internal helper
modules, and incumbent OpenClaw-specific operator entrypoints.

That distinction matters. Not every script here is a generic platform tool.

## Shared Platform Scripts

These support shared platform operations:

- `bootstrap_operator_access.sh`
- `bootstrap_vault.sh`
- `dispatch_github_workflow_from_k3s_secret.sh`
- `migrate_k8s_secret_to_vault.py`

## OpenClaw-Specific Operator Entrypoints

These are specific to the current OpenClaw product integration:

- `gateway_release.py`
- `prepull_gateway_image.py`
- `set_stage_environment_state.py`
- `validate_gateway_source_bundle.py`
- `stage_readiness.py`

They remain at the top level today because OpenClaw was the first product with
deep release automation. They should not be treated as the generic pattern for
future products.

## Internal Helper Modules

These back the OpenClaw release flow and are not intended as standalone
operator entrypoints:

- `gateway_contract.py`
- `gateway_environment.py`
- `gateway_release_ops.py`

## Current OpenClaw Release Gold Path

Use [gateway_release.py](gateway_release.py) for the current OpenClaw gateway
release flow.

Supported operator subcommands:

- `python3 scripts/gateway_release.py pin <env>`
- `python3 scripts/gateway_release.py tag <env>`
- `python3 scripts/gateway_release.py validate <env>`
- `python3 scripts/gateway_release.py record <env> --digest sha256:...`
- `python3 scripts/gateway_release.py readiness <status|reset|approve|validate>`
- `python3 scripts/gateway_release.py promote stage prod`

This is the intended OpenClaw path:

1. `pin`
2. governed GitHub build
3. `record`
4. `promote`
5. live verification

For a fixed pinned source bundle, the recorded gateway digest is expected to be
reusable across `stage` and `prod`. Promotion should reuse the approved digest
instead of rebuilding a second environment-branded image for the same bundle.

## Future Rule

As more products arrive:

- shared platform scripts should stay here
- product-specific entrypoints should either be clearly product-named or be
  documented from `products/<product>/`
