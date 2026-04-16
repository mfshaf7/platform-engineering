# platform-engineering

`platform-engineering` is the release authority for the Platform-Core stack.

It governs:

- environment contracts
- approved source SHAs
- image digests
- Argo-managed deployment state
- host provisioning for the WSL and Windows platform stack
- operator runbooks and platform standards

It does not own Telegram implementation details, bridge runtime code, or the
reference architecture for isolated deployment. It consumes those outputs and
approves what each environment runs.

## What This Repository Owns

- `environments/`
  - current approved state for `stage` and `prod`
- `scripts/gateway_release.py`
  - governed gateway release entrypoint
- `.github/workflows/`
  - build and promotion workflows
- `ansible/`
  - host provisioning and WSL stack deployment
- `charts/`
  - platform and gateway Helm packaging
- `docs/`
  - platform standards, architecture, and operator runbooks

## What This Repository Does Not Own

- Telegram channel behavior in `openclaw-telegram-enhanced/`
- host policy enforcement in `openclaw-host-bridge/`
- active runtime assembly inputs in `openclaw-runtime-distribution/`
- security standards and review authority in `security-architecture/`

## Core Workflows

### 1. Governed Gateway Release

1. Pin source repos from local canonical checkouts.
2. Validate the source bundle.
3. Build the gateway image through GitHub Actions.
4. Record the digest into `environments/<env>/versions.yaml`.
5. Let Argo reconcile the environment.
6. Verify live behavior, not just `/healthz`.

### 2. Stage Rehearsal And Promotion

1. Resume only the stage components being tested.
2. For gateway rehearsal, stage now starts its on-demand stage bridge as part of
   the stage lifecycle workflow.
3. Validate real Telegram and host-control behavior.
4. Approve stage readiness against the exact pinned candidate.
5. Promote the approved digest and SHAs into `prod`.
6. Suspend stage again when rehearsal is complete.

### 3. Host Stack Provisioning

1. Provision the WSL host stack with Ansible.
2. Keep the prod bridge always on.
3. Keep the stage bridge disabled by default and start it only during stage
   test windows.
4. Verify bridge and recovery health from the live host after provisioning.

### 4. Incident Repair

1. Classify whether the issue is source, composition, platform, or live host
   drift.
2. Contain the incident if needed.
3. Backport the fix to the owner repo.
4. Record the resulting approved state here.
5. Capture evidence in a runbook or change record when the incident materially
   changed the operating model.

## Audit And Visibility Surfaces

This repo is the main evidence surface for release and deployment truth.

- Source approval:
  - `environments/<env>/versions.yaml`
- Platform workflows:
  - GitHub Actions runs under `.github/workflows/`
- Deployment truth:
  - Argo application revision and rollout state
- Release evidence:
  - commit history for pin and digest changes
  - change records under `docs/runbooks/change-records/`
- Host provisioning evidence:
  - `ansible/` templates and playbooks
  - live WSL host verification commands in runbooks
- Observability references:
  - `observability/`

## Start Here

- Architecture:
  - [docs/architecture/overview.md](docs/architecture/overview.md)
  - [docs/architecture/control-planes.md](docs/architecture/control-planes.md)
- Standards:
  - [docs/standards/governed-change-model.md](docs/standards/governed-change-model.md)
  - [docs/standards/source-repo-contracts.md](docs/standards/source-repo-contracts.md)
  - [docs/standards/service-contracts.md](docs/standards/service-contracts.md)
  - [docs/standards/version-attestation.md](docs/standards/version-attestation.md)
- Runbooks:
  - [docs/runbooks/build-gateway-artifact.md](docs/runbooks/build-gateway-artifact.md)
  - [docs/runbooks/rebuild-and-promote-gateway.md](docs/runbooks/rebuild-and-promote-gateway.md)
  - [docs/runbooks/promote-stage-to-prod.md](docs/runbooks/promote-stage-to-prod.md)
  - [docs/runbooks/host-stack-rollout.md](docs/runbooks/host-stack-rollout.md)
  - [docs/runbooks/host-runtime-drift-recovery.md](docs/runbooks/host-runtime-drift-recovery.md)

## Common Operator Entrypoints

- `make help`
- `make gateway-pin ENVIRONMENT=stage`
- `make gateway-validate ENVIRONMENT=stage`
- `make gateway-record ENVIRONMENT=stage DIGEST=sha256:...`
- `make gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod`
- `make gateway-readiness ACTION=validate`
- `make provision-wsl-host`
- `make verify-platform-host`
- `make validate`

Use `ANSIBLE_EXTRA_VARS` when the local WSL distro or path layout differs from
the defaults.

## Repository Layout

```text
platform-engineering/
|-- .github/workflows/
|-- ansible/
|-- charts/
|-- docs/
|-- environments/
|-- observability/
|-- scripts/
`-- Makefile
```
