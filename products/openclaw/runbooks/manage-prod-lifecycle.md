# Manage Prod Lifecycle

## Purpose

This runbook defines the governed lifecycle control for the OpenClaw prod
runtime.

Supported states are:

- `live`
- `traffic-stopped`
- `suspended`
- `quarantined`

This control affects only the OpenClaw prod runtime slice:

- `openclaw-gateway-app.yaml`
- `platform-secrets-app.yaml`
- `platform-version-app.yaml`

Those managed prod Application manifests must carry
`resources-finalizer.argocd.argoproj.io` so deleting them from the prod root
also prunes the live OpenClaw runtime resources.

It must not prune unrelated prod applications such as OpenProject or shared
observability.

## Local Operator Path

Inspect the current state:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py status
```

Stop overall OpenClaw prod traffic while retaining support surfaces:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py traffic-stopped \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --note "<optional note>"
```

Suspend prod OpenClaw entirely:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py suspended \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --incident-ref "<ticket-or-incident>" \
  --note "<optional note>"
```

Quarantine prod OpenClaw during an incident:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py quarantined \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --incident-ref "<ticket-or-incident>" \
  --note "<optional note>"
```

Return prod OpenClaw to `live`:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py live \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --incident-ref "<ticket-or-incident>" \
  --note "<optional note>"
```

Equivalent Make target:

```bash
make openclaw-prod-state STATE=<live|traffic-stopped|suspended|quarantined> CHANGED_BY=<operator> REASON=<reason>
```

## GitHub Workflow Path

Use `.github/workflows/manage-prod-environment.yaml` when you want the
repository to create the lifecycle branch under the `prod` environment gate.

## Operational Effects

When prod state is `traffic-stopped`:

- `openclaw-gateway-app.yaml` is removed from the prod Argo root
- `platform-secrets-app.yaml` and `platform-version-app.yaml` remain in place
- the lifecycle configmap remains in `argocd` as explicit state evidence
- `environments/prod/verification.yaml` is reset to `inactive`

When prod state is `suspended`:

- the OpenClaw prod managed applications are removed from the prod root
- the removed OpenClaw prod Argo applications must prune their runtime
  resources instead of leaving orphaned deployments, services, or secrets
- a lifecycle configmap remains in `argocd` as explicit state evidence
- `environments/prod/verification.yaml` is reset to `inactive`
- future prod smoke/UAT remains inactive until prod is returned to `live`

When prod state is `quarantined`:

- the runtime stays down like `suspended`
- `incidentRef` is required
- prod smoke/UAT remains inactive
- promotion into prod is blocked until the lifecycle leaves quarantine

When prod state returns to `live`:

- the OpenClaw prod Argo applications are restored to the prod root
- `environments/prod/verification.yaml` is reset to `pending`
- fresh prod smoke/UAT is required before treating prod as operationally
  complete

## Promotion Interaction

Promotion may still update the prod contract while prod is `traffic-stopped` or
`suspended`.

That does not bring prod back online by itself. The lifecycle state still owns
whether the prod OpenClaw gateway is present.

This allows operators to prepare a fixed prod contract while keeping prod
quiet, then return prod to `live` only when ready.

If prod is `quarantined`, promotion is blocked by default until the lifecycle
leaves quarantine.
