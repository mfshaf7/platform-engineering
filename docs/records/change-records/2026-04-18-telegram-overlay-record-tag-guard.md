# 2026-04-18 telegram overlay record tag guard

## Summary

Hardened the stage Telegram overlay record flow so the operator must supply the
exact built overlay tag together with the digest. This closes the gap that let
an older overlay build digest be recorded against a newer pinned Telegram source
commit.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `openclaw-telegram-enhanced`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- overlay record guard owner: `platform-engineering`
- Telegram source owner: `openclaw-telegram-enhanced`

## Root Cause

The `telegram_overlay_experiment.py record` path accepted a digest without
requiring the explicit built tag from the `Build Telegram Overlay Image`
workflow. That let a previous overlay build digest be recorded while the stage
contract was already pinned to a newer Telegram source commit. Stage then
mounted an older Telegram runtime even though the contract claimed the newer
source was active.

## Source Changes

- `products/openclaw/scripts/telegram_overlay_experiment.py`
- `docs/workflows/build-telegram-overlay-image.md`
- `products/openclaw/runbooks/stage-telegram-overlay-experiment.md`
- `products/openclaw/scripts/README.md`
- `products/openclaw/skills-src/openclaw-governed-delivery/SKILL.md`

## Artifact And Deployment Evidence

- broken recorded stage overlay digest:
  - `sha256:42d69b5649ecf187d6d456dad5282463a5900a580a40f0a87c320c78703bc8c5`
- stage contract pinned Telegram source SHA at failure time:
  - `8dca54ed1268bda7d97d0f8eee9930d57fe1f11e`
- live mounted Telegram runtime still exposed the older source shape:
  - `IDEA_CAPTURE_COMMAND`
  - `/v1/workflows/idea-capture`

## Guardrail

- `telegram_overlay_experiment.py record stage` now fails unless:
  - `--tag` is supplied explicitly
  - the supplied tag matches the currently pinned Telegram source commit

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`
- `python3 products/openclaw/scripts/gateway_release.py validate stage`
- negative proof:
  - `python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage --digest sha256:42d69b5649ecf187d6d456dad5282463a5900a580a40f0a87c320c78703bc8c5`
  - now fails with `telegram overlay record requires --tag ...`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- rebuild the Telegram overlay from the currently pinned stage source
- record the correct digest with the matching explicit tag
- re-run stage rehearsal for `/idea help`, `/idea list`, `/idea show <idea-id>`,
  and `/idea <text>`
