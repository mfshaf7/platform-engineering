# Workspace Governance Control Fabric Operations

## Current Operational Posture

WGCF has local dev-integration operations only.

Current operations are local-k3s dev-integration:

- launch, inspect, smoke, and suspend the active local-k3s dev-integration API
  and PostgreSQL profile
- run project validation in the implementation repo
- run unit tests in the implementation repo
- use local CLI status, graph, plan, check, and receipt-list commands
- keep `.wgcf/` artifacts local and ignored unless a governed evidence path
  explicitly captures them
- use WGCF validator invocation only through the active profile gates in
  [validator-invocation-gates.md](validator-invocation-gates.md)

Shared runner commands:

```bash
make devint-up PROFILE=governance-control-fabric
make devint-status PROFILE=governance-control-fabric
make devint-smoke PROFILE=governance-control-fabric
make devint-access PROFILE=governance-control-fabric
make devint-down PROFILE=governance-control-fabric
```

The profile runs PostgreSQL as persistent local-k3s state and runs database
migrations before the API rollout is considered available.

## Deployment Readiness Checklist

Before platform deployment work starts, confirm:

- a platform-owned deployment ADR or release record exists
- `security-architecture` has reviewed identity, secret, runtime, AI, and
  artifact-custody boundaries
- PostgreSQL schema ownership, migrations, backup, restore, and rollback are
  defined
- validator invocation profiles are approved for the intended lane
- worker execution remains disabled unless Temporal runtime semantics are
  approved
- OPA inputs and policy ownership are defined without copying authority truth
  into WGCF
- artifact custody is denied by default until MinIO or S3 retention and
  redaction rules are approved
- observability uses existing platform surfaces instead of a custom backend
- Prometheus remains the current health and metrics surface; OpenTelemetry
  correlation can be added later without replacing platform observability
- the Governance Operations Console remains future scope unless a separate UI
  item approves it

## Failure Handling

If local WGCF validation or receipt generation fails:

- fix the implementation repo first
- keep ART completion evidence compact and receipt-linked
- do not use platform deployment as a workaround for missing local proof

If a future platform runtime fails:

- classify whether the failure is implementation, dependency, identity,
  policy, storage, or platform release drift
- contain live runtime impact first
- backport the durable fix to the owning repo
- record platform evidence through the release-governance path before claiming
  the runtime healthy

## Escalation Owners

- implementation defect: `workspace-governance-control-fabric`
- deployment state or promotion gate: `platform-engineering`
- workspace authority mismatch: `workspace-governance`
- security boundary or acceptance issue: `security-architecture`
- ART work-state or Review Packet transport issue: `operator-orchestration-service`
