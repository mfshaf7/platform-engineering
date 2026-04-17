# Telegram Overlay Artifact Lane

## Purpose

This runbook describes the bounded Telegram overlay artifact lane for small
Telegram-only fixes on a platform-qualified OpenClaw base.

Use it when:

- the change is isolated to `openclaw-telegram-enhanced`
- rebuilding the full gateway image would slow stage rehearsal unnecessarily
- you want to qualify and optionally promote a Telegram-only delivery artifact
  without rebuilding the gateway image

Do not use it to qualify a new OpenClaw base image. New base lines still go
through the full gateway path first.

## Guardrails

- immutable overlay artifact digest only
- no same-id global user-home Telegram override
- prod promotion is allowed only when the same overlay digest is approved on
  stage and tied to the same qualified base image carried into prod
- disable the lane and return to the normal gateway path when the next change
  is not a Telegram-only fix

## Gold Path

1. Pin the Telegram overlay source commit:

```bash
cd /home/mfshaf7/projects/platform-engineering
python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage \
  --telegram-repo /home/mfshaf7/projects/openclaw-telegram-enhanced
```

This also pins the current `openclaw-runtime-distribution` commit so the
workflow builds the overlay artifact from the runtime-distribution revision that
contains the matching packager and Dockerfile.

2. Dispatch `Build Telegram Overlay Image`.

3. Record the built digest:

```bash
python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage \
  --digest sha256:<overlay-digest>
```

4. Resume stage if needed and rehearse the affected Telegram capabilities.

5. Capture stage verification evidence against the current candidate.

6. If the current stage candidate is approved and the same base image is headed
   to prod, promote the approved stage candidate:

```bash
python3 products/openclaw/scripts/gateway_release.py promote stage prod
python3 products/openclaw/scripts/gateway_release.py prod-verification record \
  --verified-by "<operator>" \
  --evidence-ref "<ticket-or-telegram-ref>" \
  --check-results "reconciliation-state=passed,primary-user-path-smoke=passed,operator-surface-smoke=passed"
```

7. If the next change should return to the standard gateway lane, disable the
   overlay lane:

```bash
python3 products/openclaw/scripts/telegram_overlay_experiment.py disable stage
```

## Required Verification

At minimum:

- Telegram provider starts cleanly in stage
- normal Telegram reply works
- any changed Telegram operator surface or routing path works
- file or screenshot delivery works when the change could affect those seams

## Evidence

The stage contract should be able to answer:

- which Telegram source commit was pinned for the lane
- which overlay image digest was mounted
- which qualified OpenClaw base image the overlay was approved against
- which stage candidate and verification record covered the lane
- whether the same approved overlay digest was promoted to prod
