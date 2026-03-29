# Rollback Runbook

1. revert the environment version file to the previous approved state
2. merge the rollback pull request
3. confirm Argo CD reconciles back to the earlier revision
4. rerun host-side Ansible if the rollback includes host integration changes
5. verify runtime and observability return to the expected baseline

For a live host-stack migration rollback, use:

- [migrate-to-platform-core.md](migrate-to-platform-core.md)
