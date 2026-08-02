# Change Records

## Purpose

This directory stores short evidence records for production-impacting changes.

These are not full incident diaries. They are structured completion records for
governed fixes.

Use a change record when a production issue required one or more of:

- source fix
- rebuilt gateway image
- prod digest promotion
- Argo rollout
- host/runtime drift repair

Source-only admission does not create deployment evidence. The Temporal
controlled-proof issuer and executor under ART #792 are indexed by
[ADR-018](../../decisions/adr/ADR-018-permit-gated-component-commissioning-proof.md),
the finalized source Review Packet, and the component operations guide; a
change record becomes required only when a later authorized proof changes live
runtime state.

## Goals

Each record should make it easy to answer:

- what failed
- what layer owned the fix
- what source commits changed
- what immutable artifact was built
- what revision was deployed
- what live verification proved the result

## Naming

Use:

- `YYYY-MM-DD-short-slug.md`

## Rules

- Keep records short and factual.
- Link to the owning repos and runbooks instead of duplicating long
  explanations.
- Link the related ADR when the governed change implemented or superseded a
  shared design decision.
- Separate source/artifact fixes from host/runtime drift fixes.
- If a live-only emergency repair happened first, record both:
  - the emergency action
  - the governed follow-up that made it durable
- If the record is being used as security remediation evidence, add the
  optional `security_evidence` YAML front matter so `security-architecture`
  can consume it without a sidecar file.

## Required sections

Every record should include:

1. Summary
2. Classification
3. Ownership
4. Root cause
5. Source changes
6. Artifact and deployment evidence
7. Live verification
8. Follow-up actions

## Optional Structured Metadata

When a change record should also act as structured security remediation
evidence, add YAML front matter before the heading:

```yaml
---
security_evidence:
  review_areas:
    - runtime
  findings:
    - F-006
  risks:
    - R-006
  workstreams:
    - WS-006
---
```

This metadata is optional for ordinary rollout evidence and expected only when
another repo links the change record as machine-readable remediation evidence.
