---
security_evidence:
  review_areas: [runtime, delivery, ai]
  reviewed_artifacts:
    - dev-integration/profiles/governed-ai-gateway/runtime/model_configuration.py
    - scripts/test_api_provider_connections.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Preserve current connection admission during settings restoration

## Summary

Bounded corrective source maintenance discovered during Epic1363 integration.
Landing Unit Decision: child_isolated_landing_unit,
maintenance-provider-connection-history-1363. No new ART child or mechanism.
The isolated merged-source reproduction changed only temporary test state.

## Classification

Source-only correction before the new provider integration is commissioned.
Reuse the current owner validation boundary; no new permissions or runtime gate.

## Ownership

Platform owns connection admission and atomic configuration mutation. Console
requires current configuration references to resolve to admitted backend records.
Security1371 will review this exact merged owner source before Platform1381
commissions the composed provider work. Existing account qualification is unchanged.

## Root Cause

Route validation checked current backend admission, while backend registration
validation checked only record identity. A saved revision with a removed
connection and no selected route could therefore restore its metadata. Credentials
and invocation admission stayed fenced, but the current Console registry contract
would reject the orphan reference. The candidate was not activated.

## Source Changes

Validate every proposed backend reference against current owner admission before
the atomic configuration write. Reject an inadmissible restoration with the
current configuration, revision, history and credentials untouched. Preserve the
original historical snapshot. The regression test exercises create/register,
connection removal and attempted restoration through the real owner objects.

## Artifact And Deployment Evidence

Source-only maintenance linked to Epic1363; no runtime or account change.
The reviewed PR and exact source head provide landing evidence. Existing composed
Security acceptance and commissioning remain required for operating claims.

## Live Verification

Focused provider/custody and broader owner checks precede source publication.
Controlled proof is not a claim of live API entitlement. Real-account provider
qualification remains explicitly pending and Experimental.

## Follow-Up

Bind the correction's merged Platform head in Security1371's composed acceptance,
then commission through1381. Revoke the maintenance credential and retire its
worktree and branches. No alternate restoration interface or extra story is added.
