---
security_evidence:
  review_areas:
    - runtime
    - delivery
  reviewed_artifacts:
    - products/governance-operations-console/scripts/agent_console_platform.py
    - products/governance-operations-console/scripts/test_agent_console_platform.py
  findings: []
  risks: []
  workstreams:
    - WS-007
  notes: The verifier now contains each loopback tunnel in a dedicated process group and removes the complete group on every exit.
---

# Agent Console Port-Forward Cleanup

## Summary

Repairs the Agent Console operating verifier so failed or completed proof runs
cannot leave child `kubectl port-forward` processes holding the fixed loopback
ports used by later evidence acquisition.

## Classification

- area: Governance Operations Console platform commissioning
- type: owner-repo maintenance
- runtime impact: local `dev-integration` verification cleanup only

## Ownership

- owner repo: `platform-engineering`
- related ART slice: #1246 under Feature #1215 and Epic #1203
- related products or components: Governance Operations Console, Operator Orchestration Service, Context Governance Gateway

## Root Cause

- immediate failure: the next verifier connected to a stale tunnel on port 38180 and failed during readiness.
- actual root cause: terminating the `k3s` wrapper did not terminate the child `kubectl` process that owned the socket.
- why it escaped earlier controls: unit coverage proved policy and revision bindings but did not assert process-tree cleanup around the port-forward context manager.

## Source Changes

- changed workflow, adapter, or contract: each port-forward now starts in a new process group and cleanup signals the entire group, with bounded escalation to `SIGKILL`.
- tests or validator added: exact process-group startup and cleanup assertions.
- related change records: `docs/records/change-records/2026-10-09-agent-console-platform-admission.md`

## Artifact And Deployment Evidence

- source-only change, or build/deployment evidence: owner-repo maintenance Landing Unit `maintenance/agent-console-port-forward-cleanup`
- image tag or digest: None
- runtime revision: None; the verifier is a host-side Platform evidence command

## Live Verification

- local validation: focused verifier tests, Platform repository validation, and base-aware change-record validation
- live or dev-integration verification: repeat #1246 operating evidence and confirm both fixed loopback ports are released afterward
- residual risk: forced cleanup remains bounded to the dedicated process group created by this verifier

## Follow-Up

- required follow-up: close the linked improvement candidate after the #1246 proof succeeds and confirms no orphaned tunnel
- owner: `platform-engineering`
- due date or closure condition: before Feature #1215 and Epic #1203 close
