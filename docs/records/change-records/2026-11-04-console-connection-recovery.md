---
security_evidence:
  review_areas: [runtime]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_backend_connection.py
    - products/governance-operations-console/scripts/console_cross_domain_activation.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-005]
---

# Recover stalled Console backend connections

## Summary

Both live and preview Console servers share Platform's loopback OOS/WGCF
connections. A running but unresponsive tunnel must recover without manual
intervention or backend workload restart.

## Classification

Operator-authorized repair of existing local runtime outside active ART work.
Landing Unit: `feature_single_landing_unit`,
`maintenance-console-connection-recovery`. The pending Console UI batch remains
unpublished. Recommendation: extend existing services; no new daemon, timer,
endpoint, principal or network exposure.

## Ownership

Platform owns connections and the
[complete-runtime procedure](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).
The concrete
[composed Console Security review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md)
governs exact source acceptance before activation.

## Root Cause

On November 4 both UI shells returned HTTP200 while owner reads timed out. OOS
responded directly; its running port-forward logged stream-creation timeouts.
Connection-only restart restored data, then the fault recurred approximately
nine minutes later. `Restart=on-failure` observes process exit, not transport
responsiveness. A later pod replacement did exit the tunnel and ordinary
systemd recovery worked; that is a separate failure shape.

The precise trigger inside Kubernetes1.30.2's streaming transport is unproven.
[Upstream kubectl1620](https://github.com/kubernetes/kubectl/issues/1620)
reports the same non-exiting failure after cancelled requests on1.30. This is
a diagnostic lead, not proof of the local trigger. Available memory and direct
owner responsiveness did not support application crash/source corruption.

## Source Changes

The same two user services supervise one tunnel child each. Existing namespace,
service, ports and loopback binding remain. A fixed unauthenticated `/healthz`
read has a two-second timeout, ten-second interval, twenty-second initial grace
and three-consecutive-transport-failure threshold. Any HTTP response proves
transport responsiveness; an unhealthy backend is not reported healthy or used
to recycle a working tunnel. Redirects and environment proxies are not followed.
No response data or credentials are logged.

On persistent silence the supervisor terminates/reaps its child process group,
escalates after three seconds, then exits for a five-second-delayed systemd
restart. Unexpected zero exits recover too. Repeated failures do not permanently
latch connection services; retries retain their fixed delay. Stop/suspension
stops supervision and children. No business request is replayed, workload
restarted, credential renewed or owner authority bypassed.

`refresh-connections` extends the existing complete-runtime command under exact
source validation and the lifecycle lock. It replaces only connection units,
without rebuilding the frontend or activating the composition. Its receipt is
explicitly connection-only, not full operating or application-readiness proof.
Normal activation writes the same supervised units.

## Artifact And Deployment Evidence

Agent Gary authors/publishes; standing delegated human authority reviews/merges.
Exact merged Platform source/tree acceptance and the generated Security
owner-record index land before native activation. Private receipts retain
publication/qualification evidence. No container or Kubernetes workload changes.

## Live Verification

Tests cover a real frozen child that stays alive, stop cleanup, unexpected zero
exit, HTTP503, redirect denial and connection-only activation boundaries.
Native proof freezes a managed tunnel child, then checks automatic replacement
and Console reads without manual restart. Both backend connections use the same
supervision. Deliberate stop must stay stopped.

## Follow-Up

This repairs missing automatic recovery; it does not prove the internal stream
freeze trigger eliminated or promise no transient request failure. Preserve
truthful errors and original request identities. A reviewed cluster/transport
upgrade is separate. Rollback restores the previous accepted Platform/Security
source pair and refreshes the two connections through the matching procedure.
