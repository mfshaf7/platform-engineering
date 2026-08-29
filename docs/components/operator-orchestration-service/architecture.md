# Operator Orchestration Service Architecture

## Role

`operator-orchestration-service` is a shared internal broker that keeps
workflow orchestration out of fast-changing channel adapters such as
`openclaw-telegram-enhanced`.

It owns:

- bounded workflow APIs
- workflow correlation and audit
- OpenProject-facing workflow writes
- admitted durable workflow definitions and versioning
- aggregate run control, projection, and final receipts
- future provider-agnostic AI-assist orchestration

It does not own:

- Telegram delivery or chat UX
- workspace contract mutation
- platform rollout authority
- governed AI policy
- durable runtime lifecycle, persistence, or deployment

The component now participates in governed stage and prod release control
through release-state objects that point back to the shared deployment
contract, even though the runtime is still one shared control-plane instance
today.

## Current Live Shape

- namespace: `operator-orchestration-service`
- Argo application: `operator-orchestration-service`
- primary service: `operator-orchestration-service.operator-orchestration-service.svc.cluster.local:8080`
- secret delivery:
  - Vault role: `platform-operator-orchestration-secrets`
  - External Secret: `operator-orchestration-service-secrets`

The repository-custody workflow uses a separate, bounded provider identity:

- dedicated GitHub App installation identity
- GitHub API destination pinned to `https://api.github.com`
- exact repository scope on every issued token
- only `Metadata: read` repository permission
- Platform-owned private-key custody and short-lived token delivery
- no personal token, ambient `gh` session, or browser-held provider credential

The source contract remains disabled for normal operation until the Platform
identity evidence and Console composition under ART #1044 and #1045 are both
accepted. See [repository-provider-identity.md](repository-provider-identity.md).

Repository creation uses a second organization-bound GitHub App with exactly
`Administration: write` and `Contents: read`. It has separate Vault custody,
runtime projection, and revocation so read-only custody never inherits mutation
authority. See
[repository-provisioning-identity.md](repository-provisioning-identity.md).

## Model

The current admitted model is:

- stage OpenClaw Telegram adapter calls the broker through an internal ClusterIP
  service
- the broker authenticates callers with a broker-owned shared secret and caller
  id allowlist
- the broker writes to the canonical OpenProject backlog project
- the broker does not yet expose AI-assisted triage as a governed AI path
- no Temporal runtime is connected or admitted

The proposed durable model keeps Temporal replaceable behind OOS:

- OOS accepts workflow requests and owns business workflow behavior
- Temporal provides scheduling, replay, timers, persisted waits, and activity
  retry dispatch
- domain services retain authority over bounded activities
- Governance Operations Console calls OOS and never calls Temporal directly

See [../temporal/architecture.md](../temporal/architecture.md).

## Read With

- [../../../products/openproject/idea-backlog-contract.md](../../../products/openproject/idea-backlog-contract.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/governed-ai-access-model.md](../../standards/governed-ai-access-model.md)
- [release-governance.md](release-governance.md)
