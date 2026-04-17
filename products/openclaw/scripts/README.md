# OpenClaw Scripts

This directory contains OpenClaw-specific operator entrypoints and helper
modules for the platform integration.

These scripts are product-scoped. They are not shared platform tooling.

The reusable operator workflow for this path is published separately under
`../skills-src/`.

## Operator Entrypoints

- `gateway_release.py`
- `prepull_gateway_image.py`
- `set_prod_environment_state.py`
- `set_stage_environment_state.py`
- `telegram_overlay_experiment.py`
- `validate_gateway_source_bundle.py`

## Internal Helper Modules

- `gateway_contract.py`
- `gateway_environment.py`
- `gateway_release_ops.py`
- `prod_lifecycle.py`
- `prod_verification.py`
- `stage_readiness.py`

## Supported OpenClaw Make Targets

- `make openclaw-gateway-prepull-image ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-tag ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-pin ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-validate ENVIRONMENT=<stage|prod>`
- `make openclaw-gateway-record ENVIRONMENT=<stage|prod> DIGEST=sha256:...`
- `make openclaw-gateway-verification ACTION=<status|reset|record|validate>`
- `make openclaw-gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod`
- `make openclaw-gateway-prod-verification ACTION=<status|reset|record|validate>`
- `make openclaw-gateway-readiness ACTION=<status|reset|approve|validate>`
- `make openclaw-telegram-overlay-status`
- `make openclaw-telegram-overlay-pin TELEGRAM_REF=<git-ref>`
- `make openclaw-telegram-overlay-validate`
- `make openclaw-telegram-overlay-record DIGEST=sha256:...`
- `make openclaw-telegram-overlay-disable`
- `make openclaw-prod-state STATE=<live|suspended|status>`
- `make openclaw-stage-state STATE=<resume|suspend|status> COMPONENTS=gateway,version`

## Release Gold Path

1. `openclaw-gateway-pin`
2. governed GitHub build
3. `openclaw-gateway-record`
4. `openclaw-gateway-verification ACTION=record`
5. `make openclaw-gateway-readiness ACTION=approve`
6. `openclaw-gateway-promote`
7. `openclaw-gateway-prod-verification ACTION=record`

For a fixed pinned source bundle, the recorded gateway digest is expected to be
reusable across `stage` and `prod`. Promotion should reuse the approved digest
instead of rebuilding a second environment-branded image for the same bundle.

## Telegram Overlay Artifact Lane

The Telegram overlay artifact lane is a bounded operator path for small
Telegram-only fixes on a platform-qualified OpenClaw base:

1. `openclaw-telegram-overlay-pin`
2. `Build Telegram Overlay Image` workflow
3. `openclaw-telegram-overlay-record`
4. stage rehearsal against the recorded overlay artifact
5. readiness approval for the current stage candidate when the qualified base
   matches
6. optional `stage -> prod` promotion of the same approved overlay artifact
7. `openclaw-gateway-prod-verification ACTION=record`

The pin step must update both:

- the Telegram source commit for the overlay payload
- the `openclaw-runtime-distribution` source commit that supplies the overlay
  packager and Dockerfile used by the workflow
- the qualified OpenClaw base image already pinned in the stage contract

## Stage Release-State Objects

- `environments/stage/release-candidate.yaml`
  - exact built stage candidate for the current source bundle
- `environments/stage/verification.yaml`
  - structured stage rehearsal evidence for that candidate
- `environments/stage/promotion-readiness.yaml`
  - approval decision against that exact candidate and verification record
- `environments/prod/verification.yaml`
  - structured post-promotion prod smoke or UAT evidence for the current prod
    contract

## Prod Lifecycle Control

OpenClaw prod now has a governed runtime lifecycle separate from stage:

- `environments/prod/openclaw-lifecycle.yaml`
  - Git-managed desired prod OpenClaw lifecycle state
- `products/openclaw/scripts/set_prod_environment_state.py`
  - product-scoped controller that applies the lifecycle contract to the prod
    Argo root
- `.github/workflows/manage-prod-environment.yaml`
  - manual gated workflow that creates the lifecycle branch under the `prod`
    environment gate

The initial bounded states are:

- `live`
- `suspended`

This control only affects the OpenClaw prod runtime slice. It must not prune
OpenProject or unrelated shared prod services.
