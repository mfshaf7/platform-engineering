---
security_evidence:
  review_areas: [delivery, runtime, ai]
  findings: []
  risks: []
  workstreams: [WS-007]
  reviewed_artifacts:
    - dev-integration/profiles/governed-ai-gateway/scripts/common.sh
    - dev-integration/profiles/governed-ai-gateway/scripts/up.sh
    - docs/runbooks/dev-integration-profiles.md
  notes: "Existing bounded gateway ConfigMap deployment repair. Exact-source Security acceptance and live activation follow owner merge."
---

# Gateway runtime ConfigMap deployment

## Summary

- Date: 2026-11-18
- Short title: apply large gateway runtime without client annotation duplication
- Environment: local dev-integration
- Landing Unit Decision: `feature_single_landing_unit`, `maintenance-governed-ai-configmap-apply-20261118`

## Classification

Owner-repo maintenance repairing the existing approved Console publication.
Platform owns the admitted gateway profile. No new ART item, feature, shared
service, model, provider, privilege or storage boundary is introduced.

## Ownership

- Owning repo: Platform Engineering, existing governed AI gateway profile.
- Related repo: Security Architecture for exact composed source acceptance.
- Existing architecture: the approved local gateway/profile composition.

## Root Cause

Native activation rejected `governed-ai-gateway-app` because client-side apply
copies its content into an annotation limited to 262,144 bytes. The current
rendered runtime has 337,473 data bytes; its compact JSON exceeds that annotation
limit while remaining below the ConfigMap data limit. Source-only rendering and
provider-schema tests do not exercise Kubernetes annotation admission.

## Source Changes

Retain the full rendered manifest and all configuration contents. Split out only
the exact namespace/name-bound runtime ConfigMap for server-side apply under the
profile's field manager. Field takeover is restricted to this Platform-owned
runtime object; all other documents retain normal client-side apply. This
preserves existing selection/configuration replacement semantics, including
updates to the dynamic model selection field, without broad force-apply.

## Artifact And Deployment Evidence

Native Kubernetes dry-run must accept the complete current manifest using this
exact split path, without object mutation. Compare split documents with the
original to prove complete configuration and resource preservation. Run owning
profile/AI/runtime tests and committed local base-aware governance checks before
Gary publication. Merge Platform before regenerating the Security index and
updating the existing exact source/tree acceptance. Activate via the existing
retained complete-runtime service; source proof does not predeclare readiness.

## Live Verification

Native server dry-run passes for all 16 exact rendered resources with zero
mutations, retaining every original resource and all 337,473 runtime data bytes.
The previous client-side path failed the native annotation limit. Accepted-source
activation and full live readback remain pending; rendering is not readiness.

## Host Or Runtime Recovery

Restore the previous accepted source/configuration through normal activation.
Server-side deployment creates no new state store or data migration; preserve
all existing audit storage, owner data and original failed rollout evidence.
Do not delete runtime objects or trim the schema to evade admission.

## Security evidence

The fresh [coordinated Console review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-18-console-advisor-execution-catalog.md)
must bind this deployment amendment and exact merged Platform source/tree before
live activation. No broader acceptance, production grant or authority is implied.

## Follow-Up

- Required: exact-head CI, owner merge, regenerated Security index, existing
  composed acceptance refresh, normal activation and live qualification.
- Owner: existing Platform and Security owners.
- Residual limitation: this fixes native configuration deployment, not recurring
  hardware instability or the separate future runtime initiative.
