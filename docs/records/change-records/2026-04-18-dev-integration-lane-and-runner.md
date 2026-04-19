## Summary

Added the shared `dev-integration` lane standard and local-`k3s` runner so
cross-repo workflows can be iterated locally without using governed `stage` as
the design lab.

## Classification

- change type: platform standard and shared runner
- lane: `dev-integration`
- governed impact: stage handoff only; no governed runtime promotion

## Ownership

- source of truth for lane policy: `workspace-governance`
- shared runtime runner: `platform-engineering`
- first concrete profile owner: `operator-orchestration-service`

## Root Cause

The workspace was using governed `stage` to discover basic API, command, and
integration-shape mistakes. That made fast iteration expensive and polluted the
governed lane with early design churn.

## Source Changes

- added [../../standards/dev-integration-lane.md](../../standards/dev-integration-lane.md)
- added [../../../scripts/dev_integration.py](../../../scripts/dev_integration.py)
- updated the shared Make targets and repo guidance to expose `devint-*`
- updated the canonical OpenProject backlog runner to emit custom field ids for
  reusable local seeding

## Artifact And Deployment Evidence

- no governed stage or prod artifact was built in this change
- the runner targets local `k3s` only and records local session manifests under
  `.dev-integration/`

## Live Verification

- repo structure and governance-doc validation cover the new shared runner and
  standard
- the lane is designed to prove runtime shape locally before any governed stage
  handoff

## Follow-Up

- finish the first concrete `idea-workflow` profile in
  `operator-orchestration-service`
- record the trust-boundary review in `security-architecture`
- validate the end-to-end profile and promotion-check flow locally
