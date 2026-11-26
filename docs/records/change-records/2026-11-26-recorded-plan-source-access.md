---
security_evidence:
  review_areas: [delivery]
  findings: []
  risks: []
  workstreams: [WS-007]
  reviewed_artifacts:
    - scripts/agent_source_identity.py
    - scripts/test_agent_source_intent.py
  notes: Aligns Platform source credential identifiers with reviewed Delivery work while preserving exact intent and hash-based custody.
---

# Source access for approved Technical Plan groups

## Summary

The existing source-access issuer accepts the Delivery identifier carried by
an approved Technical Plan. The credential, receipt and revocation keep the
exact identifier supplied in the reviewed intent.

## Classification

Platform owner maintenance. The Landing Unit Decision is
`feature_single_landing_unit`.

## Ownership

Platform owns credential issuance and revocation. Delivery owns the work
group and approves its scope. The Console presents that exact scope.

## Root Cause

The issuer accepted a shorter character set than the Delivery identifier
contract. A work group from an approved plan can have a namespaced identifier,
which the existing source authorization would reject.

## Source Changes

Use the Delivery identifier alphabet within the size limit already used by
source intents. The issuer still uses a digest for private directory names.
Existing repository, branch, approval and caller checks continue to apply.

## Live Verification

Verify an approved multi-item work group can receive source access for its
reviewed OOS repository and branch. Confirm that session start uses the
same identifier and plan digest.

## Artifact And Deployment Evidence

Pair this change with the OOS and Console work-start revisions in the
existing complete-runtime Security review.

## Follow-Up

Retain exact source receipt and work session readback with the live rehearsal.
