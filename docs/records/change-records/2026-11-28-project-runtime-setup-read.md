---
security_evidence:
  review_areas:
    - identity
    - delivery
    - runtime
  workstreams:
    - WS-003
---

# Read the admitted setup for a saved project

## Summary

The Broker can read the saved-project setup from the existing authenticated
Platform provider before capturing an exact saved draft.

## Classification

Owner maintenance prerequisite for Epic #1384's Prototype integration. The
landing unit is `1384-project-runtime-setup-read`. The approved Console
work group remains `landing-unit:1384-prototype-integration`.

## Ownership

Platform checks current exact project admission and retained setup. The Broker
binds the operator's source session and submitted saved revision. The Platform
response contains the project, subject, scope, setup revision and the existing
snapshot file and byte limits. It contains no dependency cache, credentials,
host paths, runtime output or filesystem contents.

## Root Cause

The runtime provider accepted exact operations but exposed no current setup
read to the component that captures and dispatches the saved draft.

## Source Changes

The operation reads existing private data. It preserves the same provider
authentication, accepted-source and artifact-recovery gates as Run. It accepts
only the exact admitted scope and subject and matches them to the setup store.
Live activation remains governed by the Epic's publication checkpoint.

## Artifact And Deployment Evidence

The provider HTTP tests exercise admitted setup readback, wrong project,
wrong subject, changed repository scope and a subsequent real owner command
through the existing provider handler. Existing setup, snapshot and lifecycle
tests cover retained state and dispatch behavior.

## Live Verification

The focused tests used a disposable authenticated Platform HTTP provider.
The normal Console composition still requires connected rehearsal and
publication approval before enabling project runtime.

## Follow-Up

Revert this landing unit to remove the setup read route. It creates no store
format or state migration. Rehearse the Broker consumer and normal Console
route in the isolated composition before publication.
