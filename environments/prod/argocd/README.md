# Prod Environment

This directory holds the prod Argo CD overlays and application set for the
current platform stack.

OpenClaw prod now has a governed lifecycle contract:

- `environments/prod/openclaw-lifecycle.yaml`
- `products/openclaw/scripts/set_prod_environment_state.py`
- `.github/workflows/manage-prod-environment.yaml`

Current bounded states:

- `live`
- `suspended`

The prod lifecycle control only governs the OpenClaw prod slice:

- `openclaw-gateway-app.yaml`
- `platform-secrets-app.yaml`
- `platform-version-app.yaml`

It must not prune unrelated prod applications such as OpenProject, shared
observability, or shared data-plane services.

Suspending prod OpenClaw:

- removes the governed OpenClaw prod Argo applications from the prod root
- leaves a lifecycle configmap behind in `argocd` for explicit state evidence
- resets `environments/prod/verification.yaml` to `inactive`

Returning prod OpenClaw to `live`:

- re-adds the governed OpenClaw prod Argo applications
- resets `environments/prod/verification.yaml` to `pending`
- requires fresh prod smoke/UAT before treating prod as operationally complete
