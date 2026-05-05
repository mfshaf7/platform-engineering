# Context Governance Gateway Operations

## Current Operational Posture

CGG has no approved platform runtime operations today.

Current platform operations are limited to:

- checking that no CGG Argo app, namespace, Service, worker, database, object
  store, dashboard, or model-facing adapter has been created outside the
  release gate
- reviewing the inactive release-state records under
  `environments/shared/context-governance-gateway/`
- routing runtime implementation back to the owner repo and ART items
- using the security review output before approving platform service mode

## Primary Checks

For the current blocked posture, operators should check:

```bash
git status --short
python3 scripts/validate_repo_structure.py --repo-root .
python3 scripts/validate_governance_docs.py --repo-root .
```

When a future active profile exists, this document must be updated with the
exact shared runner checks such as `devint-status`, `devint-smoke`, and
`devint-promote-check` for `PROFILE=context-governance-gateway`.

## Common Failure Signals

- a CGG namespace, Service, Deployment, PVC, or object store exists without a
  matching release-state record
- a release record claims candidate or readiness while security review remains
  blocked
- raw operational context appears in platform logs, dashboards, issue notes, or
  model prompts
- a downstream adapter requests raw artifacts by default
- debug override has no operator, reason, expiry, receipt, or ledger event
- retention deletion removes raw artifacts without preserving audit metadata

## First Response

1. Stop treating the live, proposed, or build-admitted runtime as approved for
   launch.
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
- storage custody and retention decision
- validation commands and results
- rollback or suspension action when runtime drift occurred

## Related Procedures

- [release-governance.md](release-governance.md)
- [artifact-custody-and-retention.md](artifact-custody-and-retention.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
- [../../standards/dev-integration-lane.md](../../standards/dev-integration-lane.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
