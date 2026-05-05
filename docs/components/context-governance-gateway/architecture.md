# Context Governance Gateway Architecture

## Role

CGG is a shared context-admission component. Its platform role is to make raw
operational context governable before it is projected into operators, AI
systems, CI, automation, OOS, WGCF, or future dashboards.

CGG is not:

- a logging backend
- a custom scanner
- an LLM gateway
- a platform approval authority
- an ART mutation authority
- a security acceptance authority

## Target Runtime Shape

The durable service-mode target is:

- API service for capture, pack, project, inspect, receipt lookup, and ledger
  metadata reads
- worker process for bounded background redaction, scanner orchestration,
  projection, receipt emission, and retention jobs
- PostgreSQL or approved metadata store for manifests, packets, receipts,
  profile decisions, and ledger metadata
- MinIO or S3 compatible artifact store for raw and redacted artifact custody
  when shared custody is approved
- OPA/Rego policy evaluation after policy integration is approved
- scanner integrations such as Presidio, Gitleaks, and TruffleHog as
  integrated tools, not custom replacements
- existing platform observability surfaces for metrics, logs, and traces
- downstream adapters that receive model-safe or operator-safe packets, not raw
  artifacts by default

## Current Runtime Posture

Current allowed posture:

- owner-repo local CLI/source behavior
- local `.cgg` artifacts controlled by the operator
- build-admitted but non-launchable dev-integration profile
- platform release-state gate records with inactive or blocked posture

Current denied posture:

- no `stage` or `prod` Argo application
- no API listener
- no worker runtime
- no shared metadata store
- no shared raw or redacted artifact store
- no dashboard upload or browsing
- no broker, WGCF, CI, or model adapter runtime
- no direct model invocation

## Dependency Readiness

| Dependency | Platform role | Readiness rule |
| --- | --- | --- |
| Dev-integration profile | Fast local service-shape iteration | `build-admitted` authorizes bounded implementation only. The profile must be `active` in the workspace registry before shared runner launch. |
| PostgreSQL | Metadata, manifests, packets, receipts, profile decisions, and ledger metadata | Use only after schema ownership, migration, backup, restore, retention, and deletion gates are defined for CGG. |
| MinIO or S3 | Raw and redacted artifact custody | Use only after encryption, access, retention, deletion, legal hold, backup, restore, and audit posture are approved. |
| OPA/Rego | Context-admission policy evaluation | Use as a policy evaluator; do not move workspace policy truth out of `workspace-governance`. |
| Scanner integrations | Secret and sensitive-context detection | Integrate existing tools without making them the authority for projection. CGG admission policy still fails closed when uncertain. |
| Observability | Health, metrics, logs, and traces | Use existing platform observability. Do not introduce a custom observability backend. |
| Downstream adapters | Packet delivery to operators or tools | Send packet, receipt, denial, and audit metadata. Do not request raw artifacts by default. |

## Environment Path

CGG should mature through these lanes:

- local source and CLI validation in the implementation repo
- proposed, build-admitted, then active `dev-integration` profile for fast
  local service-shape iteration
- governed `stage` only after platform and security gates approve deployment
- governed `prod` only after stage evidence, release readiness, support
  readiness, backup, restore, and rollback gates pass

`dev-integration` is not governed rollout evidence and must not be described
as stage or prod readiness.

## Non-Goals

The platform deployment shape must not:

- implement CGG service mode before its security and platform gates are
  complete
- deploy object storage or PostgreSQL as a convenience workaround
- copy raw operational context into platform logs, dashboards, release records,
  or model prompts
- replace WGCF, OOS, security acceptance, workspace contracts, or governed
  model-access controls
- expose a dashboard or API before identity and authorization controls are
  approved
