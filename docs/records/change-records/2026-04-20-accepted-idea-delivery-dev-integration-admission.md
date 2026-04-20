## Summary

Accepted the `accepted-idea-delivery` profile as the second active shared
`dev-integration` lane and completed the platform-owned local OpenProject
seeding surfaces it depends on.

## Classification

- change type: local dev-integration profile admission
- lane: `dev-integration`
- governed impact: stage handoff only; no governed runtime promotion

## Ownership

- shared local-k3s runner and profile acceptance: `platform-engineering`
- concrete profile owner: `operator-orchestration-service`
- profile lifecycle registry: `workspace-governance`
- trust-boundary review owner: `security-architecture`

## Root Cause

The accepted-idea delivery workflow had a bounded broker route and a defined
OpenProject delivery model, but it still lacked an admitted local lane that
could prove the proposal-to-delivery handoff against disposable canonical
project models. That left platform-owned delivery-plane assumptions unproven in
the standard fast-iteration path.

## Source Changes

- added the canonical OpenProject delivery ART seeding runner and runbook
- extended the OpenProject identity runner so the broker can hold bounded local
  access to both `workspace-proposals` and `workspace-delivery-art`
- updated the shared dev-integration operator runbook so the second active
  profile is discoverable from the primary platform operator surface

## Artifact And Deployment Evidence

- no governed stage or prod artifact was built in this change
- the local lane still targets disposable `k3s` namespaces, generated local
  identities, and profile-owned session artifacts only

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `make devint-up PROFILE=accepted-idea-delivery`
- `make devint-smoke PROFILE=accepted-idea-delivery`
- `make devint-promote-check PROFILE=accepted-idea-delivery`

## Follow-Up

- keep the broker-local profile scripts aligned with the platform-owned
  OpenProject seed runners
- treat this admission as local-lane truth only; governed stage delivery
  rehearsal remains a later handoff step
