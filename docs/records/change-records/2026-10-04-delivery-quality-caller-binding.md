---
security_evidence:
  review_areas:
    - identity
    - delivery
  reviewed_artifacts:
    - products/openproject/scripts/openproject_check_delivery_art_quality.py
    - products/openproject/scripts/test_openproject_check_delivery_art_quality.py
    - products/openproject/runbooks/check-delivery-art-quality.md
  findings: []
  risks: []
  workstreams:
    - WS-007
  notes: "The repair consumes only credentials already projected into the OOS pod, pairs bound callers with their exact secret, retains the unbound shared-secret compatibility path, and emits no credential material."
---

# 2026-10-04 Delivery quality caller binding

## Summary

Repair the Platform Delivery ART quality adapter so identity-bound OOS callers
use their matching credential instead of being paired with the compatibility
shared secret.

## Classification

- area: OpenProject Delivery ART quality projection
- type: operator adapter identity correction
- runtime impact: scoped and portfolio quality reads authenticate through the
  active OOS caller model without weakening its distinct-secret invariant

## Ownership

- owner repo: `platform-engineering`
- tracking reference: `operator-maintenance:delivery-quality-caller-binding-2026-10-04`
- related components: OpenProject platform adapter and OOS broker

## Root Cause

- the adapter selected the first value from `CALLER_ALLOWED_IDS`
- the active profile now binds every allowed caller to an exact entry in
  `CALLER_AUTH_SECRETS_JSON`
- the adapter still sent `CALLER_AUTH_SHARED_SECRET`, so OOS correctly rejected
  the mismatched identity with `caller_auth_invalid`

## Source Changes

- select the first allowed caller with an exact caller-specific secret
- use the shared secret only with an allowed caller that has no bound entry
- fail closed when neither valid pairing exists
- document and test the identity-selection invariant

## Security Judgment

- no new identity or privilege is introduced
- no secret leaves the OOS container or appears in command output
- exact caller binding remains authoritative when present
- the compatibility shared-secret path cannot impersonate a bound caller

## Artifact And Deployment Evidence

- focused Platform unit tests
- product and repository validators
- live bounded proof returned HTTP 200 for the review-pack route using an exact
  in-pod caller binding

## Live Verification

- final proof: the normal projection sync quality command for Epic 1203
- expected result: authenticated broker projection with quality evaluated by
  OOS rather than `caller_auth_invalid`

## Rollback

Revert the source commit. Do not restore the mismatched first-caller/shared-
secret behavior; use a known valid unbound caller only if the compatibility
runtime contract explicitly provides one.

## Follow-Up

- regenerate the Security change-record index after the Platform owner change
  merges
- close the linked self-improvement regression only after merged-main live
  quality proof passes
