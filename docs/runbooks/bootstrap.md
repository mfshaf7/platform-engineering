# Bootstrap Runbook

## Purpose

This runbook describes the target bootstrap path for the full platform stack.

## Phase 1: Prepare Source Repositories

1. Clone:
   - `platform-engineering`
   - the product source repos required for the target release
2. Confirm each repo is at the intended reviewed commit.
3. Record candidate SHAs in [environments/prod/versions.yaml](../../environments/prod/versions.yaml).

## Phase 2: Bootstrap Infrastructure Inputs

1. Review Terraform variables for the isolated environment.
2. Apply Terraform from [terraform/environments/prod](../../terraform/environments/prod).
3. Confirm the cluster endpoint, registry settings, and Argo CD bootstrap inputs are ready.

Primary entrypoint:

- `terraform -chdir=terraform/environments/prod apply`

## Phase 3: Bootstrap Cluster Control Plane

1. Install Kubernetes on the isolated VM.
2. Install Argo CD.
3. Install External Secrets Operator.
4. Install Prometheus and Grafana.
5. Register the root Argo application from [argocd/apps/root.yaml](../../argocd/apps/root.yaml).

Primary assets:

- [environments/prod/argocd/kustomization.yaml](../../environments/prod/argocd/kustomization.yaml)
- [argocd/apps/root.yaml](../../argocd/apps/root.yaml)
- [argocd/bootstrap/README.md](../../argocd/bootstrap/README.md)

## Phase 4: Prepare The WSL Host Side

1. Ensure WSL runs with `systemd`.
2. Install bridge and recovery dependencies.
3. Install `systemd` units for bridge and recovery.
4. Install or verify Windows Task Scheduler bootstrap.
5. Verify local bridge and recovery health.

Primary Ansible entrypoints:

- [ansible/playbooks/provision-k3s-node.yml](../../ansible/playbooks/provision-k3s-node.yml)
- [ansible/playbooks/provision-wsl-host.yml](../../ansible/playbooks/provision-wsl-host.yml)

## Phase 5: Build And Publish Artifacts

1. Build the runtime image from pinned component versions.
2. Publish the image to GHCR.
3. Publish or update chart metadata if required.
4. Record the image tag and digest in [environments/prod/versions.yaml](../../environments/prod/versions.yaml).

Primary workflow:

- [.github/workflows/build-and-validate.yaml](../../.github/workflows/build-and-validate.yaml)

## Phase 6: Promote Production

1. Update [environments/prod/versions.yaml](../../environments/prod/versions.yaml).
2. Merge the promotion pull request.
3. Let Argo CD reconcile the cluster.
4. Run Ansible if host-side service changes are part of the release.
5. Verify Prometheus targets and Grafana dashboards are healthy.

## Phase 7: Verify

Verify all of:

- Argo CD apps are `Healthy` and `Synced`
- workload is healthy
- External Secrets are materialized
- Prometheus scrape targets are healthy
- Grafana is reachable
- host bridge is reachable from the runtime
- recovery is reachable from the runtime
- runtime version reporting matches the pinned manifest

## Documentation Rule

Each bootstrap or rollout change must update:

- this runbook
- [docs/implementation-log.md](../implementation-log.md)
- affected manifests or playbooks
