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
   - `python3 products/openclaw/scripts/gateway_release.py pin stage`
   - governed GitHub build
   - `python3 products/openclaw/scripts/gateway_release.py record stage --digest ...`
   - deliberate stage resume through `set_stage_environment_state.py`
   - real stage behavior checks
   - `python3 products/openclaw/scripts/gateway_release.py verification record ...`
   - readiness approval when stage evidence is good
   - `python3 products/openclaw/scripts/gateway_release.py promote stage prod`
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
- Keep stage suspended by default outside deliberate rehearsal windows.
- Real behavior checks matter more than `/healthz` alone.

## Scope Boundary

- Use this skill only for OpenClaw's fully governed delivery path.
- If the task stops at source-only or platform-integrated work, say that
  clearly instead of implying a full rollout happened.
