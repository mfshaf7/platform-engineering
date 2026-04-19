## Summary

Swept `platform-engineering` for current-vs-legacy and shared-vs-product drift,
then hardened the repo around the misses that escaped earlier checks.

## Classification

- change type: platform documentation and validator hardening
- environment: shared platform control plane and OpenClaw platform integration
- governed impact: operator truth and repo-boundary control only; no workload
  rollout

## Ownership

- owning repo: `platform-engineering`
- shared platform structure and validator owner: `platform-engineering`
- product-local OpenClaw host rollout owner: `platform-engineering/products/openclaw`

## Root Cause

Recent platform changes landed in partial slices. Legacy migration helpers were
isolated, but the repo still had validator blind spots around:

- unexpected shared component directories
- repo-local markdown link hygiene
- product-specific operator runbooks drifting back into shared `docs/runbooks/`
- stale live topology docs that no longer matched the current `k3s` state
- a leftover legacy `tmux` package in the WSL bootstrap defaults

## Source Changes

- updated `repo-structure-manifest.yaml` and `scripts/validate_repo_structure.py`
  to govern `operator-orchestration-service`, reject unexpected shared
  components, and enforce repo-safe markdown links
- updated `scripts/validate_operational_docs.py` and `scripts/README.md` to
  validate the shared-vs-product host-runbook boundary, reject legacy `tmux`
  bootstrap defaults, validate shared component index coverage, and provide an
  optional live-cluster topology audit
- moved the OpenClaw host rollout runbook from `docs/runbooks/` to
  `products/openclaw/runbooks/`
- refreshed the live platform topology and operator access docs against the
  current `2026-04-19` cluster state
- clarified the documentation truth model so target architecture, declared
  desired posture, and observed live reality are not treated as the same
  surface
- corrected remaining local-absolute and cross-repo-relative markdown links in
  platform change records and ADRs

## Artifact And Deployment Evidence

- no workload artifact was rebuilt
- no Argo application or host service was mutated by this sweep
- evidence is the repo diff plus the new validator coverage and refreshed live
  operator docs

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root . --check-live-cluster`
- live cluster inventory matched the refreshed `docs/architecture/current-platform-topology.md`
  for Argo applications and namespaces

## Follow-Up

- continue the repo-by-repo consistency sweep from this stronger platform base
- keep using the live-cluster topology audit when the local platform exposure
  state changes
