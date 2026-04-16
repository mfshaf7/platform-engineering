# Scripts

## Official Gateway Release Entry Point

Use [gateway_release.py](gateway_release.py) for normal gateway release work.

Supported operator subcommands:

- `python3 scripts/gateway_release.py pin <env>`
- `python3 scripts/gateway_release.py tag <env>`
- `python3 scripts/gateway_release.py validate <env>`
- `python3 scripts/gateway_release.py record <env> --digest sha256:...`
- `python3 scripts/gateway_release.py readiness <status|reset|approve|validate>`
- `python3 scripts/gateway_release.py promote stage prod`

This is the intended gold path:

1. `pin`
2. governed GitHub build
3. `record`
4. `promote`
5. live verification

For a fixed pinned source bundle, the recorded gateway digest is expected to be
reusable across `stage` and `prod`. Promotion should reuse the approved digest
instead of rebuilding a second environment-branded image for the same bundle.

## Internal Helper Modules

Gateway release plumbing now lives behind internal helper modules instead of
separate operator-facing scripts:

- `gateway_contract.py`
- `gateway_environment.py`
- `gateway_release_ops.py`
- `stage_readiness.py`

The old one-off gateway release scripts were removed to keep the operator
surface focused on `gateway_release.py`.
