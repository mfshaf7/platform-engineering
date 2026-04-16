# Stage Telegram Overlay Experiment

## Purpose

This runbook describes the bounded stage-only Telegram overlay experiment for
small Telegram-only fixes.

Use it when:

- the change is isolated to `openclaw-telegram-enhanced`
- rebuilding the full gateway image would slow stage rehearsal unnecessarily
- you want stage evidence for a Telegram-only delivery artifact before deciding
  whether the pattern should graduate further

Do not use it for prod promotion.

## Guardrails

- stage only
- immutable overlay artifact digest only
- no same-id global user-home Telegram override
- no promotion to prod while the experiment is active
- disable the experiment and return to the normal gateway path before any
  standard `stage -> prod` promotion

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

6. Disable the experiment before any normal prod promotion:

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

- which Telegram source commit was pinned for the experiment
- which overlay image digest was mounted
- which stage candidate and verification record covered the experiment
- when the experiment was disabled again
