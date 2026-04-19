# Deploy Runbook

This runbook is for shared platform deployment procedure only.

Generic deploy sequence:

1. update the target environment contract
2. merge the approved change
3. verify Argo CD sync and health
4. verify workload health, secrets, and observability targets
5. record the deployment result

## Product-Specific Note

If a deployment flow is specific to one product’s runtime or release model, it
should be documented from that product directory.

Examples:

- OpenClaw release and promotion flows now live under
  [products/openclaw/runbooks/](../../products/openclaw/runbooks/README.md)
- OpenProject access and lifecycle runbooks now live under
  [products/openproject/runbooks/](../../products/openproject/runbooks/README.md)
