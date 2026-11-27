---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
    - runtime
  workstreams:
    - WS-003
---

# Scoped GitHub repository reads

## Summary

Platform uses a shared, finite Source App read lease for the governance
checkpoint, Publication freshness, and protected source inspections.

## Classification

Maintenance of existing credential custody and read workflows. Landing unit
`github-read-consistency-platform`.

## Ownership

Platform owns the GitHub App key, exact read lease, and revocation. OOS owns
Console workflow decisions and their durable results.

## Root Cause

The maintenance issuer and Publication timer depended on anonymous GitHub
observations. Exhaustion could block an otherwise authorized maintenance
request or remove Publication freshness.

## Source Changes

The issuer uses the reviewed Workspace Governance repository identity for
its read lease and rechecks the current revision before write issuance.
Publication checks the registered owner and preserves its stale-source
distinction. Retained Git owner controls and Prototype transfer evidence
use the protected reader with independent current authority.

## Artifact And Deployment Evidence

Candidate source is in an isolated worktree. Local owner and cross-service
tests cover scoped reads, changing authority, throttling, and revocation.

## Live Verification

The configured Source App issued and revoked read-only grants for both the
Workspace Governance and registered Little List repositories. Its reads
returned current canonical main for both.

## Follow-Up

Review the exact source and qualify the candidate in the accepted Console
composition before rolling out the paired Platform and Broker changes.
