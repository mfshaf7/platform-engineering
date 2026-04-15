# Platform Engineering

`platform-engineering` is the shared platform control-plane repository fo
governed runtime delivery, GitOps reconciliation, DevSecOps controls, and
observability across managed environments.

It exists to solve the release and runtime drift problem that showed up in the
current delivery model:

- source repos changed
- deployment copies changed
- live runtime changed
- operators could not prove which version was actually running

This repository defines the approved runtime shape, release policy, security
guardrails, observability standards, and deployment control model.

## Chosen Stack

This repository standardizes on:

- GitHub for source control and approvals
- GitHub Actions for CI, packaging, and promotion automation
- GHCR for immutable OCI artifacts
- Terraform for environment and cluster bootstrap inputs
- Kubernetes for workload orchestration
- Argo CD for GitOps reconciliation and drift visibility
- Helm for workload packaging
- External Secrets Operator for runtime secret delivery
- Prometheus and Grafana for observability
- Ansible for WSL and host-side service configuration
- `systemd` for bridge and recovery ownership inside WSL

## Repository Role

This repository owns:

- approved environment state
- release version pinning
- Argo CD application layout
- Helm charts and overlays
- Terraform bootstrap definitions
- Ansible host-configuration playbooks
- observability assets
- security and governance policies
- architecture and runbooks

It does not replace the source repositories:

- `openclaw-telegram-enhanced`
- `openclaw-host-bridge`
- `openclaw-isolated-deployment`

## Architecture Summary

```text
GitHub repos
  -> GitHub Actions
  -> GHCR artifacts
  -> Terraform bootstrap
  -> Argo CD
  -> Kubernetes cluste
  -> Product workloads + observability

Windows/WSL host
  -> Ansible
  -> systemd
  -> host bridge + host recovery
```

This gives a clean separation:

- source repos own code
- this repo owns approved deployment state
- Argo CD owns cluster reconciliation
- Ansible owns host-side configuration
- runtime must reconcile back to what is declared here

## Start Here

Read in this order:

1. [docs/architecture/overview.md](docs/architecture/overview.md)
2. [docs/standards/product-boundaries.md](docs/standards/product-boundaries.md)
3. [docs/standards/source-repo-contracts.md](docs/standards/source-repo-contracts.md)
4. [docs/standards/release-model.md](docs/standards/release-model.md)
5. [docs/standards/restart-survival.md](docs/standards/restart-survival.md)
6. [docs/runbooks/bootstrap.md](docs/runbooks/bootstrap.md)
7. [docs/runbooks/build-gateway-artifact.md](docs/runbooks/build-gateway-artifact.md)
8. [docs/runbooks/migrate-to-platform-core.md](docs/runbooks/migrate-to-platform-core.md)
9. [docs/runbooks/restart-validation.md](docs/runbooks/restart-validation.md)
10. [docs/runbooks/vault-recovery.md](docs/runbooks/vault-recovery.md)
11. [docs/runbooks/vault-auto-unseal.md](docs/runbooks/vault-auto-unseal.md)
12. [docs/runbooks/bootstrap-transit-vault.md](docs/runbooks/bootstrap-transit-vault.md)
13. [docs/runbooks/access-grafana.md](docs/runbooks/access-grafana.md)
14. [docs/runbooks/change-records/README.md](docs/runbooks/change-records/README.md)

Historical records live under [docs/archive/README.md](docs/archive/README.md).

Gateway rollout note:

- `prod` gateway is a single-node host-port workload. Safe cutover depends on warming the exact target digest before the prod contract change is pushed, then letting Argo reconcile the `Recreate` rollout.
- `Build Gateway Image` produces the artifact only. `python3 scripts/record_gateway_image.py prod ...` performs the required external pre-pull before it writes the prod digest.

Common operator entrypoints:

- `make help`
- `make provision-wsl-host`
- `make provision-k3s-node`
- `make capture-cutover-evidence`
- `make render-cutover-command-inventory`
- `make render-cutover-record`
- `make render-runtime-container-verification`
- `make render-runtime-reachability`
- `make render-windows-cutover-inventory`
- `make capture-windows-task-evidence`
- `make verify-platform-host`
- `make render-windows-bootstrap`
- `make validate`
- `make show-prod-versions`

Use `ANSIBLE_EXTRA_VARS` when the fresh distro name or local paths differ from
the defaults, for example `platform_windows_wsl_distro=Platform-Core`.

## Repository Layout

```text
platform-engineering/
├── .github/workflows/
├── ansible/
├── argocd/
├── charts/
├── docs/
│   ├── architecture/
│   ├── runbooks/
│   └── standards/
├── environments/
├── observability/
├── policies/
├── products/
├── security/
├── terraform/
└── Makefile
```

Product onboarding starts in [products/README.md](products/README.md).

## Design Goal

The end state is straightforward:

- deployed versions are declared in Git
- the cluster reconciles itself to those versions
- the host side is configured idempotently
- runtime can report what is running
- observability proves health and drift state
- rollback means redeploying a previous approved version, not editing production
