---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_repository_connections.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/console_workflow_credentials.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Connected GitHub account routing

## Summary

Renew independently verified account connections inside the existing credential lifecycle.

## Classification

Operator-approved repository maintenance outside an active ART initiative. No new
ART items or improvement candidates. Landing Unit decision
`child_isolated_landing_unit`, `maintenance-repository-accounts-platform`: owner,
review, validation and rollback boundaries require separate repository landings.

## Ownership

Platform owns App verification, purpose-specific Vault custody, token delivery and renewal. Console owns the operator interface, and Security owns acceptance.

## Root Cause

This is an approved capability extension of the initial organization-only route,
not a newly invented defect. Fixed organization input did not cover operators
who use both personal and organization repositories.

## Source Changes

One installation can connect personal accounts, organizations or both, choose a
default and retain one private Registry. A single eligible destination is automatic;
multiple destinations require an explicit form selection. Verified provider account
ID/type and account-specific grant bind every operation. Existing aliases and
retained requests keep their original identity; same-named repositories stay
separate by provider ID and qualified coordinates.

Metadata, provisioning, source authoring and lifecycle authority remain separate.
Lifecycle tokens retain their explicit one-repository bound. No browser secret,
ambient credential, cross-account fallback, new service or database is introduced.

Security delta:
[Connected GitHub accounts](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-05-repository-account-routing.md).
The main agent retains Security judgment and final landing review; this is not an
independent assessment. Gary authors source and the delegated human reviews/merges.

## Artifact And Deployment Evidence

The isolated source candidate is unpublished and unactivated. Existing live source
remains accepted and unchanged. Exact PR, base-aware validation and activation
receipts must be recorded during landing and operating qualification.

## Live Verification

Candidate validation covers both account types/default selection, denied/expired
or missing grant, exact binding, provider readback, same-name collision, original
request recovery, private selection, credential renewal/consumption and truthful
visibility. Full local CI-equivalent checks and browser review remain required
before publication; no operating completion is claimed by this source record.

## Follow-Up

Land canonical Governance first and refresh governing source pins. Land OOS
before updating WGCF’s readiness consumer pin to the actual merged OOS commit;
then land WGCF, Platform and Console in dependency order. Regenerate the Security
change-record index from landed owner main before claiming closure. Normal exact
composed Security/Platform acceptance must precede live activation. Roll back the
same source/connection boundary while retaining canonical requests and evidence.

Packaged onboarding is recorded in the existing Console release backlog: ask for
personal accounts, organizations or both after installation, guide provider-native
authorization and allow later default/connection changes. Building an installer
or declaring customer setup qualified is outside this maintenance batch.


## Publication validation and installation scope

Governance producer PR321 is merged at f5e06f3c6c480ffe3d48a79f24dfe84c8d0d0e8f;
the selected custody-policy digest matches its actual merged bytes. Local owner
structure/governance checks,5 account tests,5 connection tests and91 complete-runtime
tests pass (4 existing environment skips). The CI workflow includes the new
connection tests under the existing workflow-maintenance approval
operator:repository-account-routing-batch.

Commissioning preserves the existing organization provisioning grant and existing
personal/organization metadata grants. The installation default remains its
existing organization. Personal provisioning remains unconfigured pending the
operator's separate App choice; no installation grant is widened. Live custody
history was read through its normal Console API before the connection cutover:
3 recorded requests,0 pending, with full history coverage.
