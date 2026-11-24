---
security_evidence:
  review_areas: [runtime]
  reviewed_artifacts:
    - dev-integration/profiles/temporal/scripts/render_chart_addresses.py
    - dev-integration/profiles/temporal/scripts/lib/runtime.sh
    - dev-integration/profiles/temporal/scripts/validate_source.py
  findings: []
  risks: []
  workstreams: [WS-005]
---

# Temporal startup address repair

## Summary

Keep the existing Temporal workflow namespace available during ordinary Console
startup and wait for the generated namespace job to complete.

## Classification

Platform maintenance for the active local Temporal profile. The standalone
Landing Unit is `temporal-startup-addresses-20261124`.

## Ownership

Platform owns the pinned chart render and launch. The scope is recorded in the
[composed runtime review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md).

## Root Cause

The chart supplied short DNS names to its own clients. The namespace setup
container timed out at that address while the same frontend answered at its
fully qualified name. Helm waited for Deployments and returned while the
namespace Job was pending. Later integrity confirmation encountered a
container that had yet to start and had no image identity.

## Source Changes

Qualify the chart's existing Temporal frontend environment values in the
operator's Kubernetes namespace. Use the same renderer for ordinary startup,
controlled proof, and chart validation. Startup completion includes Helm's
Job readiness check. The pinned images, service, network policy, and workflow
namespace retention are preserved.

## Artifact And Deployment Evidence

The pinned Temporal chart and image digests are reused. Merge the Platform
change and bind the exact revision through the normal Security review before
restarting the composition. The runtime activation receipt records the
operating result.

## Host Or Runtime Recovery

Use the existing Console recovery service. The restart should render and
complete the namespace Job through Helm.

## Live Verification

The incident repair proved the complete Temporal service address against the
existing registered workflow namespace. For this Landing Unit, verify the
generated Job completes and the normal Console startup receipt confirms current
core readiness. Chart validation covers all four frontend address values.

## Follow-Up

Vault operator token renewal is tracked separately from the Temporal repair.
