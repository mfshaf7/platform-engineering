---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime, ai]
  reviewed_artifacts:
    - products/governance-operations-console/complete-runtime-policy.yaml
    - products/governance-operations-console/scripts/console_model_management.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - dev-integration/profiles/governed-ai-gateway/scripts/common.sh
    - .github/workflows/build-governed-ai-runtime.yaml
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: Source-staged commissioning candidate for exact Security1319 review; deployment and operating qualification remain separate evidence.
---

# Configurable AI commissioning

## Summary

- Date: 2026-10-24
- Short title: Commission configurable model operations in the existing Console composition
- Environment: local dev-integration only
- Severity: planned capability extension

## Classification

- Type: reviewed runtime and provider-account integration
- User-facing impact: Console model registration and workflow routing become available only after the exact composed Security decision and commissioning.

## Ownership

- Owning repo or layer: Platform Engineering, ART #1320 under Epic #1313
- Related repos: OOS #1317, Console #1318 and Security #1319
- Related ADR: [ADR-030](../../decisions/adr/ADR-030-configurable-ai-task-routing.md)

## Root Cause

- Immediate failure: Initial post-PR336 activation failed because the user-systemd operator could not access the root-only k3s containerd socket for image import.
- Actual root cause: Commissioning assumed privileged local image-import access after proving only Docker construction and executable integrity. That host prerequisite was neither present nor part of the admitted operator path.
- Why it escaped earlier controls: Source and synthetic composition checks covered the image, manifest and credentials independently; actual source-image proof did not exercise deployment by the normal unprivileged operator. The repair reuses Platform's existing CI publication and Kubernetes pull path.

## Source Changes

- Repo: platform-engineering
- Commit(s): exact candidate and merged tree are bound by the Review Packet and Security decision; no future merge identifier is fabricated here.
- Guardrail added: admitted composition tests, actual native image digest validation, Kubernetes server dry-run and the primary complete-runtime procedure. The corrective maintenance also proves immutable registry selection, exact base/executable provenance, and image availability before credential effects, without a host import privilege.
- Security authority: [exact composed AI review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md); source remains pending until that decision accepts the actual candidate tree.

## Artifact And Deployment Evidence

- Build workflow run: source-local proof and the exact PR check are recorded in the Review Packet.
- Published image tag: `ghcr.io/mfshaf7/governed-ai-runtime:inputs-<fixed-input-digest>` from the existing main-only GitHub Actions/GHCR pattern. The executable and base image digests remain fixed in the source policy.
- Published digest: actual registry digest is resolved and verified before activation; source implementation alone does not claim publication or package visibility.
- Recorded prod revision: None; no stage or production activation.
- Argo application revision: None; the existing dev-integration runner owns this composition.

## Host Or Runtime Recovery

- Required host/runtime action: ensure the initial credential-free runtime package is publicly readable, use the existing complete-runtime activation after Security acceptance, then the Console's dedicated account sign-in. No containerd socket grant or sudo image import is required.
- Why it was environment drift instead of source defect: Not applicable.
- Recovery command or procedure: [Operate the complete Console runtime](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).

## Live Verification

- App health: not claimed by source validation.
- Deployed image: not claimed before exact-source activation.
- Pod: no deployment is implied by the source candidate or server dry-run.
- Functional verification: #1321 must supply real Console configuration, native provider invocations, selection evidence and recovery proof across the current profiles.
- Residual risk: private-client custody, stage/prod, direct-provider clients and model tool/action authority are outside this acceptance.

## Follow-Up

- Required follow-up: exact Security acceptance, source merge, commissioning, #1321 operating evidence and generated-index/owned-resource cleanup.
- Optional hardening: None invented for this delivery.
- Owner: Platform Engineering; Security retains its own acceptance authority.
