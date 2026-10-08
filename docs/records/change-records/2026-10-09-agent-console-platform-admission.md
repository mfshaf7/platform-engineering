---
security_evidence:
  review_areas:
    - runtime
    - identity
    - ai
    - delivery
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# Agent Console Platform Admission

## Summary

- Date: 2026-10-09
- Short title: Admit the bounded Agent Console governed-AI path
- Environment: `dev-integration`
- Severity: Planned source admission; operating activation remains gated

## Classification

Delivery ART `#1246` under Feature `#1215` and Epic `#1203`; source Landing
Unit `delivery-1203-agent-console-platform`. This extends the existing
`refinement-catalog` and governed AI gateway. It creates no new component,
composition, ART child, or architecture version.

## Ownership

Platform owns the model profile, gateway caller admission, runtime evidence
command, rollback surface, and credential-free receipt. OOS owns Agent Console
sessions and action enforcement. CGG owns model-safe projection. Console owns
the operator-facing client. Security work item `#1248` owns the exact composed
operating acceptance.

## Root Cause

The merged CGG `#1244` and OOS `#1245` implementations intentionally left
runtime admission disabled. Platform `#1246` must bind the exact caller, task,
schema, local model selection, and evidence command before the remaining
Console and Security children can complete the composition.

## Source Changes

The governed AI registry now admits only
`operator-orchestration-service/agent-console` to
`agent-console-assistant-v1` for task `assistant_response` under contract
`oos.agent-console.interaction.v1` version `1.0`. Provider output is limited to
the strict Platform-owned `{text}` schema, direct provider access remains
prohibited, and activation is local dev-integration only.

The product-local commissioning policy and `make
governance-console-agent-console` surface validate the exact existing
composition and expose deterministic positive and negative operating proof.
The live verifier requires the `#1248` Security review to bind every current
owner revision, reads the Console caller secret only from private runtime
state, uses temporary loopback port-forwards, closes its synthetic session,
and writes no credential values to the receipt.

The OOS and CGG Agent Console hooks remain default-off. Workspace composition
bindings must not enable them until `gate:agent-console-operating-acceptance`
is satisfied.

## Artifact And Deployment Evidence

- source validation: governed model-profile validation, gateway policy and runtime tests, dev-integration profile tests, Agent Console policy tests, repository structure, governance docs, operational docs, and base-aware diff validation
- deployment evidence: None before Security `#1248` and composition activation
- runtime revision: None before the exact-revision operating proof

## Live Verification

Platform's evidence profile maps the dedicated validation and test commands to
`case:agent-console-platform-protocol-positive` and
`case:agent-console-platform-protocol-negative`. It maps
`verify-operating` to `case:agent-console-operating-positive` and
`case:agent-console-operating-negative`. The latter remains blocked until the
Console candidate, Security acceptance, and Workspace Governance bindings are
merged.

## Follow-Up Actions

- merge the Platform source through human review
- complete Console `#1247` against this exact source
- complete Security `#1248` against the exact CGG, OOS, Platform, Console, and Workspace Governance revisions
- activate only the existing `refinement-catalog` bindings, run operating proof, rollback and reconcile cleanly, then finalize `#1246`
