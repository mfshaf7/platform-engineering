# OpenClaw Scripts

This directory contains OpenClaw-specific operator entrypoints and helper
modules for the platform integration.

These scripts are product-scoped. They are not shared platform tooling.

## Operator Entrypoints

- `gateway_release.py`
- `prepull_gateway_image.py`
- `set_stage_environment_state.py`
- `validate_gateway_source_bundle.py`

## Internal Helper Modules

- `gateway_contract.py`
- `gateway_environment.py`
- `gateway_release_ops.py`
- `stage_readiness.py`

## Supported OpenClaw Make Targets

- `make openclaw-gateway-prepull-image ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-tag ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-pin ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-validate ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-record ENVIRONMENT=<stage|prod> DIGEST=sha256:...`
- `make openclaw-gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod`
- `make openclaw-gateway-readiness ACTION=<status|reset|approve|validate>`
- `make openclaw-stage-state STATE=<resume|suspend|status> COMPONENTS=gateway,version`

## Release Gold Path

1. `openclaw-gateway-pin`
2. governed GitHub build
3. `openclaw-gateway-record`
4. `openclaw-gateway-promote`
5. live verification

For a fixed pinned source bundle, the recorded gateway digest is expected to be
reusable across `stage` and `prod`. Promotion should reuse the approved digest
instead of rebuilding a second environment-branded image for the same bundle.
