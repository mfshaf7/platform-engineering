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

1. Pin the source bundle from the actual local repo checkouts:

```bash
cd /home/<platform-user>/projects/platform-engineering
python3 products/openclaw/scripts/gateway_release.py pin stage
```

This helper resolves full SHAs from the local `openclaw-telegram-enhanced`,
`openclaw-host-bridge`, `openclaw-runtime-distribution`, and
`platform-engineering` checkouts, refuses dirty repos by default, synchronizes
derived values files, updates the deterministic candidate tag, clears any stale
digest from the previous build, and validates the candidate contract. Use
`--allow-dirty` only when you intentionally want to pin the current committed
HEAD while local uncommitted changes are present.

2. Validate the source bundle locally:

```bash
cd /home/<platform-user>/projects/platform-engineering
python3 products/openclaw/scripts/validate_gateway_source_bundle.py \
  --telegram-repo /home/<platform-user>/projects/openclaw-telegram-enhanced \
  --deployment-repo /home/<platform-user>/projects/openclaw-runtime-distribution
```

3. Trigger the governed build workflow:

```bash
gh workflow run "Build Gateway Image" \
  --repo <repo-owner>/platform-engineering \
  --ref main \
  -f environment=prod
```

4. Wait for the workflow to complete successfully and capture the digest from the build summary or logs.

5. Warm the exact target digest and record it into the prod contract in one step:

```bash
cd /home/<platform-user>/projects/platform-engineering
PLATFORM_SHA="<platform-engineering-build-commit>"
python3 products/openclaw/scripts/gateway_release.py record prod \
  --digest sha256:<published-digest> \
  --platform-sha "$PLATFORM_SHA"
```

`gateway_release.py record` now performs three checks in one governed step:

- the tag must exactly match the deterministic source-bundle tag in `versions.yaml`
- the external pre-pull happens before the digest is written
- the environment contract is revalidated immediately after the write

That prevents stale build output from being attached to the current pins.

For stage rehearsals, use the same pattern with `stage` instead of `prod`; `gateway_release.py record stage ...` now performs the external pre-pull before it writes the stage digest too.

6. Commit and push the recorded prod values.

7. Refresh Argo if needed:

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

Functional verification for Telegram and host control is required after base
image changes or host-control contract changes. At minimum verify:

- normal stage Telegram polling and reply
- direct Telegram file delivery from a staged host file
- desktop screenshot delivery through Telegram
- host-control topic routing for a deterministic read action
- admin/high-risk host-control action only if the environment contract
  intentionally enables it

For direct Telegram file delivery, confirm the environment contract mounts the
shared host media path at `/home/node/.openclaw/media`; otherwise bridge staging
can succeed while Telegram delivery still fails inside the container.

## Required completion evidence

Capture at minimum:

- owning repo commit SHAs
- platform-engineering build commit SHA
- build run URL
- published digest
- recorded prod revision
- deployed pod image
- one functional verification result
- evidence for the Telegram/host-control behavior checks above when those seams changed

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
- keep the validato
- rerun the build only after validation passes

### Argo stays on old revision

Action:

- verify the digest record commit is pushed
- refresh the application
- check app sync revision and deployment image separately

## Rule

Do not patch the running pod as a final fix. If a new image is required, complete the rebuild-and-promote flow.
