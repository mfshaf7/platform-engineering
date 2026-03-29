# Deploy Runbook

1. update the target environment version file
2. merge the promotion pull request
3. verify Argo CD sync and health
4. verify workload health, secrets, and observability targets
5. record the deployment result

For staged rollout, use:

- [promote-stage-to-prod.md](promote-stage-to-prod.md)

For fresh host migration and cutover, use:

- [migrate-to-platform-core.md](migrate-to-platform-core.md)
