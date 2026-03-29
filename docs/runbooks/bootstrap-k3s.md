# Bootstrap k3s

## Purpose

This runbook defines the platform-managed `k3s` bootstrap path.

## Managed Inputs

- [ansible/playbooks/provision-k3s-node.yml](../../ansible/playbooks/provision-k3s-node.yml)
- [ansible/roles/k3s_node](../../ansible/roles/k3s_node)
- [terraform/environments/prod](../../terraform/environments/prod)

## Expected Outcome

After a successful run:

- `k3s` is installed
- the `k3s` service is enabled
- `k3s kubectl get nodes` succeeds
- the host is ready for Argo CD bootstrap
