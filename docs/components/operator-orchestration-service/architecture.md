# Operator Orchestration Service Architecture

## Role

`operator-orchestration-service` is a shared internal broker that keeps
workflow orchestration out of fast-changing channel adapters such as
`openclaw-telegram-enhanced`.

It owns:

- bounded workflow APIs
- workflow correlation and audit
- OpenProject-facing workflow writes
- future provider-agnostic AI-assist orchestration

It does not own:

- Telegram delivery or chat UX
- workspace contract mutation
- platform rollout authority
- governed AI policy

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

## Model

The current admitted model is:

- stage OpenClaw Telegram adapter calls the broker through an internal ClusterIP
  service
- the broker authenticates callers with a broker-owned shared secret and caller
  id allowlist
- the broker writes to the canonical OpenProject backlog project
- the broker does not yet expose AI-assisted triage as a governed AI path

## Read With

- [../../../products/openproject/idea-backlog-contract.md](../../../products/openproject/idea-backlog-contract.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/governed-ai-access-model.md](../../standards/governed-ai-access-model.md)
- [release-governance.md](release-governance.md)
