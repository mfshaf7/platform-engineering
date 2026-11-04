---
security_evidence:
  review_areas: [identity, secrets, runtime]
  reviewed_artifacts:
    - products/governance-operations-console/complete-runtime-policy.yaml
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/console_cross_domain_activation.py
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-005]
---

# Configure the existing repository reader approval reference

## Summary

Restore the missing existing-repository approval reference in Console activation.

## Classification

Operator-authorized maintenance outside active ART. Landing Unit decision:
`feature_single_landing_unit`, `maintenance-repository-link-binding`. Extend the
existing accepted lifecycle; no new workflow, identity, privilege or ART item.
Gary authors/publishes; delegated human authority reviews and merges.

## Ownership

Platform owns binding projection and runtime configuration. Console owns the
form; OOS owns command authorization; Security owns exact-source acceptance.

## Root Cause

Live and preview reported repository-custody source available but mutation
invalid with `console_authority_reference_unavailable`. Platform supplied the
creation binding but omitted the dedicated reader reference expected by Console.
The commissioned account-wide metadata reader already served real lookup.
Its private receipt, approved account contract, matching Secret and running OOS
consumer were verified before selecting the stable credential-binding digest.
No token, key or private receipt is committed.

## Source Changes

The complete-runtime policy explicitly selects that nonsecret custody reference;
resolved activation carries it separately from provisioning. Activation writes
the dedicated server environment pair. Absence withholds the pair with no
provisioning fallback. This is approval provenance, not a token or health probe;
existing reader renewal/revocation, OOS authorization, WGCF readiness and
operator confirmation still control submission. No new provider permissions.

Concrete Security references: the
[account reader review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-03-account-repository-reader.md)
and [composed Console acceptance](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md).
Exact merged source acceptance and the generated owner-record index precede
runtime activation. This source record does not claim operating success.

## Artifact And Deployment Evidence

The three source owners retain separate reviewed PRs. Runtime deployment evidence
is recorded after exact Security acceptance, not inferred from these tests.

## Live Verification

Owner checks cover separate binding projection, omission without fallback,
invalid references and identity separation; existing reader renewal tests stay
applicable. Bring the reviewed Console batch and Platform change through source
review, then Security acceptance and normal complete-runtime activation.
Verify actual capabilities, provider lookup and canonical link behavior.
Private receipts and PR evidence retain actual deployment results. Rollback uses
the previous accepted Platform/Console/Security source pair and activation.

## Follow-Up

Customer-facing account setup remains outside this maintenance slice. Selecting
another account/installation must reconcile its binding reference. A configured
reference does not establish provider health or a completed custody record.
