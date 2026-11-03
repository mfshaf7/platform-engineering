---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime]
  reviewed_artifacts:
    - security/repository-provider-identity.yaml
    - scripts/repository_provider_identity.py
    - scripts/repository_provider_account.py
    - products/governance-operations-console/scripts/console_repository_reader.py
    - products/governance-operations-console/scripts/console_workflow_credentials.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Account metadata reader maintenance

## Summary

One explicitly approved personal GitHub account or organization can provide
metadata access for existing and future repositories. Extend the existing
identity producer and credential timer; keep selected isolation available.

## Classification

Operator-authorized maintenance in local dev-integration. Landing Unit:
`feature_single_landing_unit`, `maintenance-organization-repository-reader-platform`.
No new service, ART item, installer or customer setup interface.

## Ownership

Platform owns the dedicated metadata-only App key, scope selection, short-lived
token, renewal and protected Secret delivery. OOS enforces the account and
immutable repository identity. Security's
[account reader review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-03-account-repository-reader.md)
extends the existing boundary; exact composed-source activation remains required.

## Root Cause

The metadata reader was not part of the existing credential-maintenance group,
and its selected grant excluded later private repositories. Repairing only one
repository's current token would leave the repeated manual setup unchanged.

## Source Changes

The existing producer's explicit account mode verifies native App/installation,
metadata-only permissions, account, All repositories scope and one-hour token
lifetime. Returned token scope must also be All. The protected delivery receipt
selects the connection; an absent selection enables nothing. The existing timer
renews before expiry and the existing group rollout consumes two optional
Secret references. Stale renewals cannot overwrite a changed/disconnected
selection; revocation clears the reader fields. Missing projection and matching
interrupted delivery recover under that same selection. Retire previous tokens
after consumption. Primary procedure:
[Repository Provider Identity](../../components/operator-orchestration-service/repository-provider-identity.md#account-metadata-reader).

## Artifact And Deployment Evidence

Source candidate; publication and normal activation are pending. The earlier
selected-token containment is not account-mode operating evidence. No new
minting key or token is embedded in source or this record.

## Live Verification

Source scope, renewal, disconnect races, recovery and existing runtime tests
pass. Native account commissioning verified Metadata read/All repositories and
read an existing private repository outside the earlier single-repository grant;
the proof token was revoked. Native API dry-run validates optional consumption
and reader-only removal without changing the deployment. No new live repository
was created. Automatic deployed renewal and final Console proof remain pending.

## Follow-Up

The first native activation exposed a readiness-check compatibility miss: the
reviewed Console adapter preserves OOS's canonical
`repository_custody_request_not_found` code, while Platform's negative-read probe
still expected the former generic adapter code. The actual route returned the
correct authenticated live 404 and original message; receipt-list reads worked.
Align the existing check and regression cases with that canonical response,
retaining exact HTTP status, message and live-mode checks. A wrong generic 404
must remain denied. This does not enable another workflow or relax authority.
After paired source acceptance, use the supported runtime restart and status
path; a repeated full composition bring-up is unnecessary for this probe fix.

Publish reviewed sources, update exact composed acceptance and activate through
the existing complete-runtime procedure. Verify the maintained connection,
actual consumer and live lookup. Update this record with final source/runtime
evidence. Guided customer onboarding and independent-installation qualification
remain required before customer release.
