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

That status output now summarizes the operator-relevant posture directly:

- whether `openclaw-gateway` is still present
- whether support surfaces remain live
- whether promotion is allowed
- whether prod verification is `pending` or `inactive`
- which managed prod applications are retained vs removed

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

Quick operator summary for the OpenClaw reference profile:

| State | Gateway | Support surfaces | Promotion | Prod verification | Incident ref |
| --- | --- | --- | --- | --- | --- |
| `live` | active | retained | allowed | `pending` | optional |
| `traffic-stopped` | removed | retained | allowed | `inactive` | optional |
| `suspended` | removed | removed | allowed | `inactive` | optional |
| `quarantined` | removed | removed | blocked | `inactive` | required |

For this product profile, support surfaces means:

- `platform-secrets-prod`
- `platform-version`

## Operator Selection Guide

Use `traffic-stopped` when:

- prod user traffic must go quiet
- you still want platform version and secrets evidence surfaces available
- you may still need to promote a fixed contract while prod stays quiet
- there is no incident posture requiring stricter governance

Use `suspended` when:

- you want the full OpenClaw prod slice down
- stage is the active stabilization environment for a while
- you do not need retained OpenClaw support surfaces in prod
- promotion may still proceed while prod stays offline

Use `quarantined` when:

- you suspect compromise, unsafe behavior, or a trust-boundary problem
- incident tracking must be explicit
- promotion must be blocked until containment and follow-up are complete

Return to `live` only when:

- the target prod contract is the one you intend to serve
- the reason for `traffic-stopped`, `suspended`, or `quarantined` is cleared
- you are ready to perform fresh prod smoke/UAT on the restored runtime

## Operator Follow-Through

After every lifecycle change:

1. Check the local contract summary:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py status
```

2. Check the prod root health:

```bash
k3s kubectl -n argocd get application platform-root-prod
```

3. Check the explicit lifecycle evidence:

```bash
k3s kubectl -n argocd get configmap openclaw-prod-lifecycle -o yaml
```

4. Check the remaining OpenClaw prod footprint:

```bash
k3s kubectl -n openclaw get all,cm,secret,sa
```

Treat the lifecycle configmap and remaining namespace footprint as the
authoritative live proof of what is still running.

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
