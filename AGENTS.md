# Platform Engineering Agent Notes

## Gateway Rollout Guardrails

- Treat `Build Gateway Image` as artifact creation only. A successful build does not mean prod is safe to swap yet.
- `prod` gateway is single-node and binds host port `18789`. Normal rolling updates can deadlock on port allocation.
- Do not manually delete or restart the old prod gateway pod as a first resort.
- Prod cutover must use the external pre-pull sequence: warm the exact target digest on the node first, then commit the prod contract change, then let Argo reconcile.
- `python3 scripts/record_gateway_image.py prod ...` now performs that external pre-pull before it writes the prod digest by default.
- If investigating a slow prod rollout, check the node image pull and deployment image first. Do not add a chart hook or Argo-managed pre-pull resource back onto the sync path.
- If you need a fresh gateway image, trigger `Build Gateway Image`, wait for the digest, run `record_gateway_image.py` for prod, then commit and push the resulting contract change.

## Stage Promotion Guardrails

- Keep `stage` suspended by default in source control.
- Resume only the components you are actively testing. Normal gateway rehearsal should use `gateway,version`, which activates `gateway + secrets + version`.
- Any stage lifecycle change resets promotion readiness. Treat every resume, suspend, or stage contract edit as a new approval boundary.
- Prod promotion must fail closed unless `scripts/stage_promotion_readiness.py validate` passes against the current stage candidate.
- Use `Confirm Stage Promotion Readiness` only after stage testing is complete and the current candidate is explicitly approved for prod.
- After a successful prod promotion, suspend stage again unless there is an explicit follow-up test in progress.

## Workflow Dispatch Guardrails

- Trigger GitHub Actions only from the real WSL repo state, not a stale workspace copy.
- Before dispatching a workflow on a branch, verify the remote ref exists on GitHub.
- Prefer the exact workflow file name or workflow ID when dispatching; do not rely only on the display name.
- Do not bundle branch creation, push, and dispatch into one opaque shell chain when a ref check would surface the real problem earlier.

## Workspace Source Of Truth

- Treat the WSL repos under `/home/mfshaf7/projects/...` as the primary working copies and source of truth.
- Do not assume the Windows workspace mirror is current.
- Use the Windows side only for temporary helper files or tasks that are explicitly Windows-local.
- Before making repo conclusions, checks, or workflow changes, inspect the WSL copy first.
