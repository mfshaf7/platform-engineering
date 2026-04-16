# Rebuild And Promote Gateway

## Purpose

Use this runbook when an OpenClaw fix requires a rebuilt image and the normal
governed `stage -> prod` promotion path.

This is the default path for:

- Telegram or plugin fixes
- bundled runtime composition fixes
- tracked workspace template fixes
- source-bundle compatibility fixes

## Preconditions

- the owning source repo change is committed and pushed
- the stage source bundle in `environments/stage/versions.yaml` points at the
  intended SHAs
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

3. Trigger the governed build workflow for the stage candidate:

```bash
gh workflow run "Build Gateway Image" \
  --repo <repo-owner>/platform-engineering \
  --ref main \
  -f environment=stage
```

4. Wait for the workflow to complete successfully and capture the digest from the build summary or logs.

5. Warm the exact target digest and record it into the stage contract in one step:

```bash
cd /home/<platform-user>/projects/platform-engineering
PLATFORM_SHA="<platform-engineering-build-commit>"
python3 products/openclaw/scripts/gateway_release.py record stage \
  --digest sha256:<published-digest> \
  --platform-sha "$PLATFORM_SHA"
```

`gateway_release.py record` now performs three checks in one governed step:

- the tag must exactly match the deterministic source-bundle tag in `versions.yaml`
- the external pre-pull happens before the digest is written
- the environment contract is revalidated immediately after the write

That prevents stale build output from being attached to the current pins.

For `stage`, the record step also materializes
`environments/stage/release-candidate.yaml` and resets verification and
readiness so the next approval must match the exact candidate just built.

6. Commit and push the recorded stage values.

7. Refresh stage Argo if needed:

```bash
k3s kubectl -n argocd annotate application openclaw-stage-gateway \
  argocd.argoproj.io/refresh=hard --overwrite
```

8. Verify the stage rollout:

```bash
k3s kubectl -n argocd get application openclaw-stage-gateway \
  -o jsonpath='{.status.sync.status} {.status.health.status} {.status.sync.revision}{"\n"}'

k3s kubectl -n openclaw-stage get deploy openclaw-gateway \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

k3s kubectl -n openclaw-stage rollout status deploy/openclaw-gateway --timeout=240s
```

9. Record stage verification evidence for the exact candidate:

```bash
python3 products/openclaw/scripts/gateway_release.py verification record \
  --verified-by "<operator>" \
  --evidence-ref "<ticket-or-runbook-ref>" \
  --check-results "runtime-start=passed,primary-user-path=passed,artifact-delivery=passed,screenshot-delivery=passed,privileged-path-posture=not_applicable"
```

10. Approve the verified candidate for prod promotion:

```bash
python3 products/openclaw/scripts/gateway_release.py readiness approve \
  --approved-by "<operator>" \
  --note "stage candidate verified and approved for prod promotion"
```

11. Run the governed promotion workflow:

```bash
gh workflow run "Promote Environment" \
  --repo <repo-owner>/platform-engineering \
  --ref main \
  -f source_environment=stage \
  -f target_environment=prod \
  -f suspend_stage_environment=true
```

12. Review and merge the generated prod promotion PR.

13. Verify prod after Argo reconciles the merged contract.

Functional verification for Telegram and host control is required after base
image changes or host-control contract changes. At minimum verify on stage:

- normal stage Telegram polling and reply
- direct Telegram file delivery from a staged host file
- desktop screenshot delivery through Telegram
- host-control topic routing for a deterministic read action
- admin/high-risk host-control action only if the environment contract
  intentionally enables it

For direct Telegram file delivery, confirm the environment contract mounts the
shared host media path at `/home/node/.openclaw/media`; otherwise bridge staging
can succeed while Telegram delivery still fails inside the container.

## Required Completion Evidence

Capture at minimum:

- owning repo commit SHAs
- platform-engineering build commit SHA
- build run URL
- recorded stage candidate
- recorded stage verification evidence
- readiness approval evidence
- published digest
- merged prod promotion PR or revision
- deployed prod pod image
- one prod functional verification result

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
- keep the validator result with the build evidence
- rerun the build only after validation passes

### Stage Or Prod Argo Stays On Old Revision

Action:

- verify the digest record commit is pushed
- refresh the application
- check app sync revision and deployment image separately

## Rule

Do not patch the running pod as a final fix. If a new image is required,
complete the candidate-first rebuild-and-promote flow.
