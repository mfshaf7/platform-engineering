# Verify Prod After Promotion

## Purpose

Use this runbook after a governed `stage -> prod` promotion to record
post-promotion prod smoke or UAT against the exact promoted prod contract.

This is not a replacement for stage rehearsal. Stage remains the approval gate.
Prod smoke or UAT proves the live user-facing rollout actually completed.

## Evidence Object

Record the result in:

- [../../../environments/prod/verification.yaml](../../../environments/prod/verification.yaml)

Manage it through:

- [../scripts/gateway_release.py](../scripts/gateway_release.py)

## Current Baseline Checks

The current baseline prod smoke pack is defined in:

- [../prod-verification-catalog.yaml](../prod-verification-catalog.yaml)

Required checks today:

- `reconciliation-state`
- `primary-user-path-smoke`
- `operator-surface-smoke`

## Preconditions

- the prod promotion PR is merged
- prod OpenClaw lifecycle is `live`
- Argo reports the promoted prod applications as `Synced Healthy`
- the live prod deployment image matches the promoted digest
- the promoted product is reachable through its intended operator or user path

## Manual Smoke Or UAT Pack

1. Prove reconciliation state.
   Capture:
   - prod Argo sync and health
   - prod deployment image digest
   - runtime startup or provider startup evidence for the promoted candidate

2. Prove the primary user path.
   For OpenClaw, this means one real inbound prod Telegram interaction and a
   correct reply from the promoted runtime.

3. Prove the operator surface.
   Use one read-only prod operator interaction, for example `/platform` or
   `/platform health`, and confirm it is handled natively and safely.

## Record The Result

```bash
python3 products/openclaw/scripts/gateway_release.py prod-verification record \
  --verified-by "<operator>" \
  --evidence-ref "<ticket-or-runbook-ref>" \
  --check-results "reconciliation-state=passed,primary-user-path-smoke=passed,operator-surface-smoke=passed"
```

Example evidence refs:

- `telegram://<bot-or-chat-ref>?messages=<ids>`
- `runbook://openclaw-prod-smoke-<date>`
- ticket or incident link with attached screenshots and log evidence

If a check fails or is blocked, record the real result instead of forcing a
false pass:

```bash
python3 products/openclaw/scripts/gateway_release.py prod-verification record \
  --verified-by "<operator>" \
  --evidence-ref "<ticket-or-runbook-ref>" \
  --note "Primary user path failed after promotion; rollback under review." \
  --check-results "reconciliation-state=passed,primary-user-path-smoke=failed,operator-surface-smoke=blocked"
```

## Completion Rule

For a prod-affecting OpenClaw promotion, the rollout is not operationally
complete until:

- the prod contract is reconciled
- the prod lifecycle is `live`
- the prod smoke or UAT evidence is recorded in Git
- the recorded check results satisfy the current prod verification catalog
