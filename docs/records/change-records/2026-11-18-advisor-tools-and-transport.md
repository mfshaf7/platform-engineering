---
security_evidence:
  review_areas: [ai, runtime]
  reviewed_artifacts:
    - security/schemas/advisor-draft-reply.schema.json
    - security/schemas/agent-console-response.schema.json
    - security/schemas/delivery-work-design-advice.schema.json
    - products/governance-operations-console/scripts/console_backend_connection.py
    - products/governance-operations-console/scripts/test_console_backend_connection.py
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: "Existing local composition and provider custody only; source validation is not live model-quality evidence."
---

# Advisor tool grammar and preserved long responses

## Summary

Operator-approved maintenance extends the existing native advisory grammar and
repairs a tunnel-supervision false positive. Landing Unit Decision:
`child_isolated_landing_unit`, `maintenance-advisor-transport-20261118`.
This owner has a separate validation and rollback boundary. No new service,
account, model route, effort override or ART item is introduced.

## Classification

Existing local dev-integration maintenance, separate from the pending shared
development-runtime implementation.

## Ownership

Platform owns provider reply schemas and backend connection supervision. OOS
owns workflow interpretation; Console owns local draft operations and rendering;
Security owns coordinated exact-source acceptance.

## Root Cause

The native grammar represented cards and edges but omitted useful existing
diagram operations. Separately, the tunnel supervisor killed all multiplexed
connections after one request's stream timeout, aborting an unrelated model
reply that subsequently completed in the provider's retained journal.

## Source Changes

The closed native grammar includes bounded trays, membership, same-ID connector
updates, arrangement/layer data and sizing/placement settings. It remains inert
local-draft output; no shell, browser, repository, canonical mutation or final
decision tool is granted. Existing provider bounds and account custody remain.

A stream diagnostic triggers an immediate bounded health check. Healthy active
responses remain connected. Existing repeated-health failure detection and
child cleanup still recover an actually stalled tunnel.

## Artifact And Deployment Evidence

The native schema tests check all actual provider contracts and their shared
canonical grammar. A real local delayed-response test reproduces the previous
interruption and proves original response delivery through the diagnostic.
The other hang, unhealthy HTTP and child cleanup cases remain required.
Full owner validation and exact-head CI precede Security acceptance/activation.

## Live Verification

No new source is live during implementation. Native semantic and current-source
readback follow normal coordinated accepted-source activation.

## Follow-Up

Land Platform, OOS and Console, regenerate the Security owner index and review
the exact composition, qualify actual advisor behavior, and retire source grants
and branches/worktrees before completion.

## Rollback

Select the prior accepted source set through the existing complete-runtime
lifecycle, preserving all mutable owner state and original invocation records.
