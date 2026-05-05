# Context Governance Gateway Operations

## Current Operational Posture

CGG has approved local `dev-integration` operations only after the workspace
registry marks the profile `active`.

Current platform operations are:

- checking that no CGG Argo app, stage/prod namespace, governed Service,
  dashboard, broker adapter, or model-facing adapter has been created outside
  the release gate
- launching or resuming the local-k3s dev-integration API, worker, PostgreSQL,
  MinIO, and PVC-backed CGG state only through the shared runner after
  workspace activation
- running read-only smoke against the persistent local working lane
- suspending the local dev-integration runtime while preserving PVCs and local
  secrets
- reviewing the inactive release-state records under
  `environments/shared/context-governance-gateway/`
- routing implementation defects back to the owner repo and ART items
- using the security review output before approving platform service mode

## Primary Checks

Before workspace activation, operators should check the blocked posture:

```bash
git status --short
python3 scripts/validate_repo_structure.py --repo-root .
python3 scripts/validate_governance_docs.py --repo-root .
make devint-status PROFILE=context-governance-gateway
```

When the workspace registry is `active`, use:

```bash
make devint-up PROFILE=context-governance-gateway
make devint-status PROFILE=context-governance-gateway
make devint-smoke PROFILE=context-governance-gateway
make devint-promote-check PROFILE=context-governance-gateway
make devint-down PROFILE=context-governance-gateway
```

Use `make devint-reset PROFILE=context-governance-gateway` only when you intend
to destroy the local CGG dev-integration namespace, PVC-backed local custody,
and profile state.

## Common Failure Signals

- a CGG namespace, Service, Deployment, PVC, or object store exists outside the
  active dev-integration profile or a governed release-state record
- a release record claims candidate or readiness while security review remains
  blocked
- raw operational context appears in platform logs, dashboards, issue notes, or
  model prompts
- a downstream adapter requests raw artifacts by default
- debug override has no operator, reason, expiry, receipt, or ledger event
- retention deletion removes raw artifacts without preserving audit metadata

## First Response

1. Stop treating the live, proposed, or build-admitted runtime as approved for
   launch unless the workspace registry lifecycle is `active`.
2. Identify whether the drift is source, platform deployment, storage custody,
   security review, or workspace contract drift.
3. If a live component exists outside the gate, contain the runtime first and
   route the durable fix to the owning repo.
4. Record blocker, risk, or defect state in ART when the drift blocks the
   active delivery front.

## Recovery Sequence

For accidental runtime creation:

1. capture the namespace, workload, image, storage, and access path evidence
2. preserve audit-relevant metadata without copying raw operational context
3. suspend or remove the unauthorized runtime through the platform owner path
4. backport the missing gate or implementation fix to the owner repo
5. update ART with the blocker or defect outcome

For missing release evidence:

1. keep stage or prod readiness closed
2. update the release-state record to the correct inactive, pending, rejected,
   or approved posture
3. rerun platform validation before claiming the gate is usable

## Evidence To Capture

- exact source repo, branch, PR, and merge commit
- release-state record paths and statuses
- security review reference
- storage custody and retention decision, including whether evidence is local
  dev-integration only
- validation commands and results
- rollback or suspension action when runtime drift occurred

## Related Procedures

- [release-governance.md](release-governance.md)
- [artifact-custody-and-retention.md](artifact-custody-and-retention.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
- [../../standards/dev-integration-lane.md](../../standards/dev-integration-lane.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
