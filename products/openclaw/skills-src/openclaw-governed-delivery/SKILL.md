---
name: openclaw-governed-delivery
description: Use when OpenClaw changes need to move through the governed platform path, especially from owner-repo change through stage rehearsal, readiness approval, promotion, and production evidence.
---

# OpenClaw Governed Delivery

Use this skill when an OpenClaw change must be carried through the real
platform delivery path instead of stopping at a source patch.

## Read First

- `../../AGENTS.md`
- `../../README.md`
- `../../runtime-contract.md`
- `../../visibility-and-operations.md`
- `../../scripts/README.md`

Then read the source owner's `AGENTS.md` and `README.md` before editing.

## Workflow

1. Confirm the canonical owner repo for the requested change.
2. Make and validate the owner-repo change first.
3. Update platform-side OpenClaw docs if behavior, runtime contract, or
   operator flow changed.
4. Use the governed product path:
   - normal lane:
     - `python3 products/openclaw/scripts/gateway_release.py pin stage`
     - governed GitHub build
       - prefer `scripts/dispatch_github_workflow_from_k3s_secret.sh` over raw `gh workflow run` when dispatching from the operator shell
     - `python3 products/openclaw/scripts/gateway_release.py record stage --digest ...`
   - Telegram overlay artifact lane for small Telegram fixes on a qualified base:
     - `python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage`
     - `Build Telegram Overlay Image` workflow
       - prefer `scripts/dispatch_github_workflow_from_k3s_secret.sh build-telegram-overlay-image.yaml --ref main`
     - `python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage --digest ...`
   - deliberate stage resume through `set_stage_environment_state.py`
   - real stage behavior checks
   - `python3 products/openclaw/scripts/gateway_release.py verification record ...`
   - if the Telegram overlay lane is active:
     - ensure the lane stays bound to the current qualified base image
     - allow `stage -> prod` only by reusing the exact approved overlay digest on the same base line
   - readiness approval when the standard stage contract is promotable and stage evidence is good
   - `python3 products/openclaw/scripts/gateway_release.py promote stage prod`
   - if prod OpenClaw must be kept quiet or deliberately stopped:
     - use `python3 products/openclaw/scripts/set_prod_environment_state.py live|traffic-stopped|suspended|quarantined ...`
     - for OpenClaw, `traffic-stopped` means deployment-level gateway removal with support surfaces retained, not Telegram-specific traffic gating
     - treat the prod lifecycle as separate from promotion; contract updates may happen while prod is traffic-stopped or suspended
   - `python3 products/openclaw/scripts/gateway_release.py prod-verification record ...`
   - stage suspension when appropriate
5. Record the evidence needed to explain:
   - source SHAs
   - approved digest
   - approving platform revision
   - deployed Argo revision
   - recorded stage verification evidence
   - recorded prod smoke or UAT evidence when prod changed
   - live behavior checks

## Guardrails

- Do not treat a source patch as the final fix when governed runtime behavior
  changed.
- Do not patch the running pod as the final answer.
- Do not rebuild a separate prod-branded image for the same approved source
  bundle.
- Do not promote a Telegram overlay lane that is still `pending-build` or tied to a different base image than the current stage contract.
- Do not suspend unrelated prod services when the goal is only to stop OpenClaw prod.
- Do not promote into prod while the OpenClaw lifecycle is `quarantined`.
- If live containment requires `k3s kubectl delete`, use explicit `kind/name`
  targets only and avoid mixed shorthand forms.
- Keep stage suspended by default outside deliberate rehearsal windows.
- Real behavior checks matter more than `/healthz` alone.

## Scope Boundary

- Use this skill only for OpenClaw's fully governed delivery path.
- If the task stops at source-only or platform-integrated work, say that
  clearly instead of implying a full rollout happened.
