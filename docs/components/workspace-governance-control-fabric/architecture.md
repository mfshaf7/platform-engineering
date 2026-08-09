# Workspace Governance Control Fabric Architecture

## Role

The Workspace Governance Control Fabric is a shared governance runtime
component, not a product-specific application and not a new authority source.

Its platform role is to make governance operations faster and more observable by
running implementation services that consume authority truth from other repos.
It stores runtime evidence, compact receipts, ledger events, graph projections,
and readiness decisions. It must not become the source of truth for workspace
contracts, platform promotion, security acceptance, or ART state.

## Target Runtime Shape

The durable platform target is:

- API service for status, graph, validation plan, readiness, receipt, ledger,
  and decision-explanation surfaces
- CLI for local and operator recovery workflows
- worker process for bounded background validation and receipt production
- PostgreSQL for metadata, graph state, receipts, readiness decisions, and
  ledger records
- bounded, idempotent governance activity operations that OOS-mediated durable
  workflows may invoke after activity execution is approved
- OPA/Rego for policy evaluation after policy-engine integration is approved
- MinIO or S3 for full artifact custody when enterprise mode requires raw
  artifact preservation
- OpenTelemetry-compatible telemetry and Prometheus scraping for platform
  observability
- profile-gated validator invocation that keeps direct validator rollback until
  workspace shadow parity is proven

## Current Runtime Posture

The current implementation is not deployed as a platform runtime.

Current allowed posture:

- local source validation
- local CLI status, graph, plan, check, and receipt-list commands
- local receipt and ledger files
- retained historical local-k3s `dev-integration` API and PostgreSQL proof for
  API contract and console-consumption iteration
- retained historical MinIO/S3-compatible evidence-custody proof; the current
  storage lifecycle remains dormant until workspace-registry activation reaches
  remote `main`

Current denied posture:

- no `stage` or `prod` Argo application
- no long-running worker
- no API-side validation execution
- no approval or security-acceptance authority
- no Governance Operations Console UI
- no Context Governance Gateway implementation

## Dependency Readiness

| Dependency | Platform role | Readiness rule |
| --- | --- | --- |
| PostgreSQL | Metadata, graph, receipt, readiness, and ledger state | Reuse the platform PostgreSQL pattern only after data ownership, backup, restore, and migration gates are defined for WGCF. |
| OOS and Temporal orchestration path | OOS-owned aggregate workflows may dispatch bounded WGCF validation and readiness activities through the Platform-owned Temporal runtime. | Keep activity execution non-running until OOS workflow ownership, WGCF activity idempotency, identity, retry, audit, and runtime admission are approved. WGCF must not own aggregate orchestration. |
| OPA/Rego | Policy evaluation engine | Use OPA as an evaluator of authority-backed policy inputs; do not move policy truth out of `workspace-governance`. |
| MinIO/S3 | Full artifact custody for enterprise evidence | The local profile proves isolated storage mechanics and content-address-preserving backup/restore only. Governed use still requires approved workload identity, encryption, retention, deletion, and access policy. |
| Observability | Metrics, logs, traces, and operator health | Integrate with the existing platform observability model; do not introduce a custom observability backend. |
| Validator invocation gates | Platform profile control for WGCF planned checks and receipts | Use the approved profile gates in [validator-invocation-gates.md](validator-invocation-gates.md); do not let WGCF replace direct validators without workspace shadow parity and rollback. |

## Environment Path

WGCF should mature through these lanes:

- local source validation in the implementation repo
- proposed then active `dev-integration` profile for fast local API/runtime
  iteration
- governed `stage` only after platform and security gates approve deployment
- governed `prod` only after stage evidence, release readiness, rollback, and
  support-readiness gates pass

`dev-integration` is not stage rehearsal and must not be described as governed
deployment evidence.

## Non-Goals

The platform deployment shape must not:

- build the Governance Operations Console UI in this slice
- implement the Context Governance Gateway in WGCF
- replace OpenProject, the broker, or Review Packets as ART evidence authority
- store raw operational context in WGCF unless artifact custody is explicitly
  approved
- treat compact receipts as the full enterprise evidence store
- expose direct operator access before identity and authorization controls are
  approved
- project object-store credentials or artifact bodies into OOS or OpenProject
