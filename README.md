# platform-engineering

GitOps, host provisioning, and release orchestration for the Platform-Core stack.

## Documents

1. [docs/runbooks/build-gateway-artifact.md](docs/runbooks/build-gateway-artifact.md)
2. [docs/runbooks/rebuild-and-promote-gateway.md](docs/runbooks/rebuild-and-promote-gateway.md)
3. [docs/runbooks/migrate-to-platform-core.md](docs/runbooks/migrate-to-platform-core.md)
4. [docs/runbooks/restart-validation.md](docs/runbooks/restart-validation.md)
5. [docs/runbooks/vault-recovery.md](docs/runbooks/vault-recovery.md)
6. [docs/runbooks/vault-auto-unseal.md](docs/runbooks/vault-auto-unseal.md)
7. [docs/runbooks/bootstrap-transit-vault.md](docs/runbooks/bootstrap-transit-vault.md)
8. [docs/runbooks/access-grafana.md](docs/runbooks/access-grafana.md)
9. [docs/runbooks/change-records/README.md](docs/runbooks/change-records/README.md)

Historical records live under [docs/archive/README.md](docs/archive/README.md).

## Gateway rollout note

- `prod` gateway is a single-node host-port workload. Safe cutover depends on warming the exact target digest before the prod contract change is pushed, then letting Argo reconcile the `Recreate` rollout.
- `Build Gateway Image` produces the artifact only. `python3 scripts/gateway_release.py record prod ...` performs the required external pre-pull before it writes the prod digest.
- `stage` rehearsals now use the same external pre-pull path by default, so `python3 scripts/gateway_release.py record stage ...` warms the exact target digest before the stage contract change is written.

## Stage promotion policy

- `stage` is suspended by default.
- Bring `stage` up only when you are actively testing a candidate change.
- Normal gateway rehearsal should resume `gateway,version`, which activates `gateway + secrets + version`.
- Prod promotion is blocked until the current stage candidate is explicitly approved through `Confirm Stage Promotion Readiness` and still matches `environments/stage/versions.yaml`.
- Successful prod promotion should normally suspend `stage` again.

## Common operator entrypoints

- `make help`
- `make gateway-tag ENVIRONMENT=stage`
- `make gateway-pin ENVIRONMENT=stage`
- `make gateway-validate ENVIRONMENT=stage`
- `make gateway-record ENVIRONMENT=stage DIGEST=sha256:...`
- `make gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod`
- `make gateway-readiness ACTION=validate`
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
|-- .github/workflows/
|-- ansible/
|-- charts/
|-- docs/
|-- environments/
|-- scripts/README.md
|-- scripts/
`-- Makefile
```
