---
security_evidence:
  review_areas:
    - identity
    - delivery
    - runtime
  workstreams:
    - WS-003
---

# Serve the verified saved-project preview

## Summary

The existing Platform owner serves a confirmed project run over an isolated
loopback origin when the reviewed composition admits the browser preview.

## Classification

Platform owner maintenance prerequisite for Prototype Delivery #1396.
Landing unit `1384-managed-project-preview` owns the narrow browser
transport and can be rolled back independently of private Run.

## Ownership

Platform binds a verified pod identity and its reviewed HTTP port to the
current operation. Broker carries the current owner observation and Console
displays its address. Security owns operating approval for the boundary.

## Root Cause

The Platform provider verified Kubernetes workload identity and readiness
without serving an address the Windows browser could open. The initial
rehearsal supplied a temporary test-only route.

## Source Changes

Extend the existing provider with one bounded loopback listener and a
stable hostname for each admitted project. Resolve the exact running pod
on each request under the original owner guard. Replacement and Stop retire
the previous operation. A current read can confirm and restore the address
after loss of the listener. The journal retains the source evidence and
does not persist an active address into historical observations.

The listener enforces its Host, rejects cross-origin interactive requests,
strips private headers, applies bounded request and response sizes, and
retains only host-only cookies. Embedding remains disabled.

## Artifact And Deployment Evidence

The focused Platform suite tests exact current observation, refusal of
unrelated hosts and origins, withdrawn admission, and route withdrawal.
The isolated candidate composition started and replaced two real saved
revisions through the Console server and Broker. Windows Chrome loaded
the owner address and refused other hosts, and Stop withdrew the route.

## Host Or Runtime Recovery

None for source review. On the admitted runtime, reread the original
operation to confirm an address after owner recovery.

## Live Verification

The evidence uses an isolated local project. The live composition will
require the recorded independent Security and publication checks, including
verification of the exact accepted Platform, Broker and Console source.

## Follow-Up

Withdraw the optional port binding in the supported composition rollback.
The source and run receipts remain available for history and recovery.
