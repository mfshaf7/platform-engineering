# Temporal Architecture

## Role

Temporal is a replaceable durable runtime behind
`operator-orchestration-service` (OOS). It provides scheduling, deterministic
workflow replay, persistent timers, and activity retry dispatch. It does not
decide business policy, approvals, admission, or completion truth.

```mermaid
flowchart LR
    Console[Governance Operations Console]
    OOS[Operator Orchestration Service]
    Temporal[Temporal runtime]
    WGCF[WGCF activities]
    Domains[Other bounded activity owners]
    Platform[Platform runtime controls]

    Console -->|intent and allowed controls| OOS
    OOS -->|versioned workflow definitions| Temporal
    Temporal -->|durable activity dispatch| WGCF
    Temporal -->|durable activity dispatch| Domains
    OOS -->|aggregate projection and receipts| Console
    Platform -. runtime lifecycle .-> Temporal
```

## Authority Model

OOS owns:

- versioned workflow definitions
- orchestration request acceptance
- run-control API
- correlation and causation
- aggregate run projection
- final orchestration receipts

Temporal owns:

- durable scheduling
- deterministic replay
- timers and persisted waits
- activity retry dispatch

Activity owners retain their domain authority. For example, WGCF owns
governance validation and readiness activity behavior, while OOS retains the
aggregate workflow.

## Build-Admitted Dev-Integration Shape

The first profile requests:

- local `k3s`
- one operator-scoped namespace
- Temporal service and diagnostic UI
- PostgreSQL-backed persistent workflow history
- OOS-owned workflow workers and clients connected through scoped identity
- read-only shared smoke checks

Normal `devint-down` must suspend runtime processes while preserving workflow
history. `devint-reset` is explicitly destructive and may remove only the
operator-scoped local profile state.

## Data Boundary

Temporal history is runtime state, not a new business source of truth.

Workflow payloads should carry:

- source record references and versions
- correlation and causation references
- bounded decisions and control signals
- receipt and artifact references

Workflow payloads must not carry:

- secret values
- raw operational context
- unbounded logs or artifacts
- duplicated business records that belong to an authority system

Retention, redaction, backup, restore, and visibility rules must be accepted
before runtime activation.

## Namespace And Task-Queue Boundary

- dev-integration namespaces are operator-scoped
- task queues must identify the owning workflow or activity boundary
- activation-sensitive workflow queues derive a one-way generation from the
  accepted activation-manifest digest; same-manifest restarts reuse that
  generation, while a revoked digest is never admitted again
- callers and workers must be authenticated before shared runtime admission
- one activity owner must not consume another owner's task queue accidentally
- direct Console credentials for Temporal are denied
- PostgreSQL administration credentials are separate from the non-superuser
  Temporal application identity and are not projected into Temporal pods

NetworkPolicy restricts which admitted worker identities can reach the
frontend. It does not interpret task-queue names. Queue ownership therefore
also requires owner-specific worker registration, credentials, denial tests,
and fresh Security acceptance before activation.

The source-defined namespace, task-queue, ServiceAccount, secret-reference,
payload, retention, and network contracts live under
`dev-integration/profiles/temporal/runtime/`. They remain subject to operating
proof and fresh Security acceptance before activation.

## Current Runtime Posture

Allowed now:

- source-defined and validated component, profile, persistence, identity,
  queue, payload, and operator contracts
- architecture and security review
- build-admitted status inspection

Denied now:

- runtime installation
- persistent volume creation
- workflow execution
- self-serve access
- `stage` or `prod` deployment

## Read With

- [Operator Orchestration Service architecture](../operator-orchestration-service/architecture.md)
- [../workspace-governance-control-fabric/architecture.md](../workspace-governance-control-fabric/architecture.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
- [ADR-017](../../decisions/adr/ADR-017-temporal-durable-workflow-runtime.md)
