# Record Gateway Image

Use this after the governed gateway image build publishes a new tag and digest.

## Purpose

Update the environment contract and the two runtime-facing values files in one
pass, without hand-editing YAML.

The helper now refuses to record a tag that does not exactly match the current
deterministic source-bundle tag in `versions.yaml`. That prevents a successful
but stale or wrong build output from being attached to the current source pins.

## Command

Example for `prod`:

```bash
PLATFORM_SHA="<platform-engineering-build-commit>"

python3 products/openclaw/scripts/gateway_release.py record prod \
  --digest sha256:replace-with-build-output \
  --platform-sha "$PLATFORM_SHA"
```

This updates:

- `environments/prod/versions.yaml`
- `environments/prod/values/openclaw-gateway.yaml`
- `environments/prod/values/platform-version.yaml`

`--platform-sha` should be the exact `platform-engineering` commit that the
build workflow ran on. This keeps artifact provenance accurate even when the
promotion commit is recorded later.

For `stage`, use the same command with `stage` instead of `prod`. Recording the
stage digest also updates the candidate-first release-state objects:

- `environments/stage/release-candidate.yaml`
- `environments/stage/verification.yaml`
- `environments/stage/promotion-readiness.yaml`

The stage record step materializes the current release candidate, then resets
verification and approval so rehearsal evidence and readiness approval always
match the exact candidate being promoted later.

## Required Follow-up

`gateway_release.py record` now validates the environment contract
automatically after writing. Then commit the resulting source-of-truth change
and let Argo CD reconcile the updated digest normally.
