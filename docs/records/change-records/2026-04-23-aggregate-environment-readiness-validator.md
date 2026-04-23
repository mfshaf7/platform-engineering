# 2026-04-23 Aggregate environment readiness validator

## Summary

Added a shared aggregate fail-closed environment-readiness validator and
operator workflow so `stage` and `prod` can be assessed from the exact governed
release records rather than inferred from ad hoc health checks.

This tranche adds:

- machine-readable aggregate readiness contracts for `stage` and `prod`
- a shared validator that evaluates:
  - OpenClaw product readiness through the existing product adapter
  - shared control-plane readiness records
  - platform-integrated OpenProject readiness records
  - supporting-component support-readiness records
- a top-level `make environment-readiness` operator surface
- a shared runbook for the aggregate readiness workflow

## Classification

- owner repo: `platform-engineering`
- workflow area:
  - release control
  - operator workflow
  - environment readiness

## Ownership

- aggregate environment-readiness contracts and validator:
  `platform-engineering`
- workload-specific readiness and verification records:
  the existing owning product or component contracts inside
  `platform-engineering`
- cross-cutting security judgment:
  `security-architecture`

## Root Cause

The platform already had workload-level governed records for:

- OpenClaw stage readiness and prod verification
- OpenProject stage readiness and prod verification
- `operator-orchestration-service` stage readiness and prod verification
- supporting-component support-readiness

But there was still no shared operator path that answered the higher-level
question:

- is the environment governed-ready overall right now

That gap left stage and prod vulnerable to operator reconstruction and
false-ready interpretation:

- individual workloads could remain `pending` while the environment still
  looked healthy enough from Argo or HTTP reachability
- explicit `inactive` state for intentionally suspended support surfaces had no
  aggregate consumer
- different workload tiers could drift without one fail-closed readiness
  verdict

## Source Changes

- `environments/stage/environment-readiness.yaml`
- `environments/prod/environment-readiness.yaml`
- `scripts/validate_environment_readiness.py`
- `docs/runbooks/assess-environment-readiness.md`
- `docs/standards/governed-release-control-model.md`
- `Makefile`
- `README.md`
- `scripts/README.md`
- `repo-structure-manifest.yaml`

## Artifact And Deployment Evidence

- no live deployment contract changed in this tranche
- the work adds the aggregate control that evaluates the already-governed
  workload records for stage and prod

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_governance_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_operational_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_environment_readiness.py status stage --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_environment_readiness.py status prod --repo-root /home/mfshaf7/projects/platform-engineering`
- `git -C /home/mfshaf7/projects/platform-engineering diff --check`

## Follow-Up

- record real stage and prod readiness evidence until the aggregate checks can
  pass in strict `validate` mode
- keep the stage observability and dashboard inputs explicitly `inactive` until
  those stage surfaces are deliberately resumed
- extend later workload tranches to the aggregate contracts only after they
  own real governed readiness records rather than generic health claims
