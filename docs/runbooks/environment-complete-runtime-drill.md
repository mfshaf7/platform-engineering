# Environment-Complete Runtime Drill

## Purpose

This runbook defines the shared operator surface for the
`environment-complete-runtime-drill` workflow.

Use this drill only when you are intentionally claiming estate-complete
coverage across every admitted lane and product environment in scope.

If you only need the current operator-critical stack, use
[active-stack-runtime-drill.md](active-stack-runtime-drill.md) instead.

## What Makes This Different

`environment-complete-runtime-drill` is stricter than the active-stack drill.

It includes the active operator path plus the previously omitted admitted
surfaces that make the estate claim honest:

- accepted-idea-delivery devint
- the shared non-devint broker lane
- prod OpenProject
- OpenClaw stage
- OpenClaw prod
- Vault
- External Secrets
- platform-postgresql
- prod and stage platform observability baseline
- prod and stage platform dashboard overlay
- required host-bridge surfaces

Compatibility note:

- `PROFILE=full-platform-runtime-drill` is now a compatibility alias for
  `environment-complete-runtime-drill`
- it is no longer an alias for `active-stack-runtime-drill`

## Contract Sources

- [../../environments/shared/runtime-drills/environment-complete-runtime-drill.yaml](../../environments/shared/runtime-drills/environment-complete-runtime-drill.yaml)
- [../../environments/shared/runtime-drills/environment-complete-runtime-drill-evidence-template.yaml](../../environments/shared/runtime-drills/environment-complete-runtime-drill-evidence-template.yaml)
- [../standards/governed-runtime-drill-model.md](../standards/governed-runtime-drill-model.md)

## Operator Entrypoints

```bash
make platform-drill ACTION=<plan|snapshot|activate|verify|record|restore|status> PROFILE=environment-complete-runtime-drill
```

Direct script form:

```bash
python3 scripts/platform_drill.py <action> --profile environment-complete-runtime-drill
```

Legacy compatibility alias:

```bash
make platform-drill ACTION=plan PROFILE=full-platform-runtime-drill
```

## Minimum Flow

1. Plan the drill and read the declared surfaces.
2. Capture the baseline before activation.
3. Activate only through the declared owner controls.
4. Record verification results for every required environment-complete check.
5. Hold the runtime window open until required manual testing is finished.
6. Restore the exact captured baseline.
7. Record restore proof before calling the drill complete.

## Baseline First

Never start with activation.

Start with:

```bash
make platform-drill ACTION=plan PROFILE=environment-complete-runtime-drill
make platform-drill ACTION=snapshot PROFILE=environment-complete-runtime-drill RUN_ID=<run-id> OPERATOR=<operator> NOTE="<why this estate-complete drill exists>"
```

This creates the run directory:

- `.platform-drills/environment-complete-runtime-drill/<run-id>/`

and the authoritative files:

- `run.yaml`
- `baseline.yaml`
- `verification.yaml`
- `restore.yaml`
- `evidence.yaml`

## Verification Rule

This drill is only complete when the environment-complete checks are recorded
honestly.

The minimum check set is:

- `accepted-idea-delivery-runtime`
- `shared-broker-runtime`
- `openproject-prod-runtime`
- `openclaw-stage-runtime`
- `openclaw-prod-lifecycle`
- `secrets-delivery-chain`
- `supporting-components-ready`
- `observability-prod-runtime`
- `observability-stage-runtime`
- `restore-attestation`

Each check must end as one of:

- `passed`
- `failed`
- `blocked`
- `not_applicable`

If a check is `blocked`, record one explicit enterprise decision:

- `remove`
- `workaround`
- `accept-risk`
- `defer`

## Restore Rule

This drill uses `exact-baseline` restore.

If you decide to keep the post-drill state instead of restoring the captured
baseline, the work is no longer a drill. Reclassify it as a governed change.

## Related Surfaces

- [active-stack-runtime-drill.md](active-stack-runtime-drill.md)
- [access-platform-uis.md](access-platform-uis.md)
- [../components/observability/README.md](../components/observability/README.md)
