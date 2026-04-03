# Rebuild And Promote Gateway

## Purpose

Use this runbook when a production gateway fix requires a rebuilt image and normal Argo promotion.

This is the default path for:

- Telegram/plugin fixes
- bundled runtime composition fixes
- tracked workspace template fixes
- source-bundle compatibility fixes

## Preconditions

- the owning source repo change is committed and pushed
- the prod source bundle in `environments/prod/versions.yaml` points at the intended SHAs
- source-bundle validation passes locally

## Procedure

1. Validate the source bundle locally:

```bash
cd /home/mfshaf7/projects/platform-engineering
python3 scripts/validate_gateway_source_bundle.py \
  --telegram-repo /home/mfshaf7/projects/openclaw-telegram-enhanced \
  --deployment-repo /home/mfshaf7/projects/openclaw-isolated-deployment
```

2. Compute the expected publish tag:

```bash
cd /home/mfshaf7/projects/platform-engineering
python3 scripts/compute_gateway_publish_tag.py prod
```

3. Trigger the governed build workflow:

```bash
gh workflow run "Build Gateway Image" \
  --repo mfshaf7/platform-engineering \
  --ref main \
  -f environment=prod
```

4. Wait for the workflow to complete successfully and capture the digest from the build summary or logs.

5. Record the published image into the prod contract:

```bash
cd /home/mfshaf7/projects/platform-engineering
PLATFORM_SHA="<platform-engineering-build-commit>"
python3 scripts/record_gateway_image.py prod \
  --tag prod-<computed-tag> \
  --digest sha256:<published-digest> \
  --platform-sha "$PLATFORM_SHA"
python3 scripts/validate_environment_contract.py prod --repo-root .
```

6. Commit and push the recorded prod values.

7. Refresh Argo:

```bash
k3s kubectl -n argocd annotate application openclaw-gateway \
  argocd.argoproj.io/refresh=hard --overwrite
```

8. Verify rollout:

```bash
k3s kubectl -n argocd get application openclaw-gateway \
  -o jsonpath='{.status.sync.status} {.status.health.status} {.status.sync.revision}{"\n"}'

k3s kubectl -n openclaw get deploy openclaw-gateway \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

k3s kubectl -n openclaw rollout status deploy/openclaw-gateway --timeout=240s
```

## Required completion evidence

Capture at minimum:

- owning repo commit SHAs
- platform-engineering build commit SHA
- build run URL
- published digest
- recorded prod revision
- deployed pod image
- one functional verification result

## Failure handling

### Build fails at pinned ref verification

Most likely cause:

- incorrect full commit SHA in `versions.yaml`

Action:

- correct the exact SHA
- push the pin change
- rerun the build

### Build fails at source validation

Most likely cause:

- Telegram/deployment bundle mismatch
- missing workspace template
- incompatible runtime contract

Action:

- fix the owning source repo
- keep the validator
- rerun the build only after validation passes

### Argo stays on old revision

Action:

- verify the digest record commit is pushed
- refresh the application
- check app sync revision and deployment image separately

## Rule

Do not patch the running pod as a final fix. If a new image is required, complete the rebuild-and-promote flow.
