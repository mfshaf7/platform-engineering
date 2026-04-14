# Platform Engineering Agent Notes

## Gateway Rollout Guardrails

- Treat `Build Gateway Image` as artifact creation only. A successful build does not mean prod is safe to swap yet.
- Record the immutable digest back into the target environment contract before expecting Argo to roll anything out.
- `prod` gateway is single-node and binds host port `18789`. That means normal rolling updates can deadlock on port allocation.
- Do not manually delete or restart the old prod gateway pod as a first resort. Let the chart-driven rollout strategy own the cutover.
- `prod` now enables the chart-managed pre-pull DaemonSet plus `Recreate` deployment strategy. Future digest changes must flow through GitOps so Argo runs the pre-pull before the host-port swap.
- If investigating a slow prod rollout, check the pre-pull DaemonSet and image-pull events before blaming the app code.
- If you need a fresh gateway image, trigger `Build Gateway Image`, then record the digest, then let Argo reconcile. Do not assume rebuilding alone fixes a cold node pull.
