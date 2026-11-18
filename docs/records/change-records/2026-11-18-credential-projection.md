---
security_evidence:
  review_areas: [identity, secrets, runtime]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_workflow_credentials.py
    - products/governance-operations-console/scripts/console_repository_reader.py
    - products/governance-operations-console/scripts/console_repository_connections.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: "Extend existing projected Secret consumption; no new account, grant, store, model call or activation authority. Composed security acceptance and operating proof follow source review."
---

# Keep workflow requests alive during routine credential renewal

## Summary

Approved maintenance repairs an observed long advisor request lost when routine
GitHub credential renewal changed the OOS PodTemplate. The Gateway completed the
original request; its output was recovered without repeating inference.
Landing Unit Decision: `child_isolated_landing_unit`, `maintenance-credential-projection-20261118`.
The prior units are already merged and retired; this new owner delta has its own
validation, review and rollback boundary. No ART item is introduced.

## Classification

Existing owner runtime maintenance, separate from pending development-runtime work.

## Ownership

OOS owns bounded provider consumption and account checks. Platform owns existing
Secret projection, expiry, consumption proof and renewal. Security owns exact
composed acceptance. Console drafts and final decision controls are unchanged.

## Root Cause

Expiry/resource-version annotations were placed in the PodTemplate. Kubernetes
therefore replaced OOS during token renewal, closing active requests. Remaining
repository credentials were also captured once from process environment.

## Source Changes

Use current bounded server-configured credential files per repository operation,
retaining exact account, purpose and immutable repository checks. Read the reader
account and token together from one JSON projection of the existing Secret.
Configured file failure never falls back to an old environment token. Optional
connection failure does not disable core startup or unrelated workflows.
Deployment metadata retains dynamic observations; routine GitHub token renewal
does not change PodTemplate. Configuration changes and real WGCF readiness-caller
replacement retain required rollouts because those callers still consume env.
Await projected-file consumption before retiring previous tokens, with one bounded
wait for the five required identities. Secret values stay out of argv and receipts.

## Artifact And Deployment Evidence

Real file-rotation tests prove new credentials without client reconstruction,
fail-closed removal and preserved operation generations. Platform tests compare
PodTemplates before/after forced group renewal and execute the generated probe.
Full owner checks and exact-head review precede coordinated acceptance.

## Live Verification

Source tests are not operating proof. Activate the exact reviewed composition;
prove actual renewal preserves the OOS pod and an in-flight advisor response.
Original recovered model output is validated/rendered without inference replay.

## Follow-Up

Complete exact composed acceptance, operating proof, grant revocation and cleanup.

## Rollback

Restore the previous reviewed source set through normal composition activation.
Retain existing private selections, credentials, drafts and provider journals.
A rollback may require one explicit service rollout; never replay unknown work.
