# Change Records

## Purpose

This directory stores short evidence records for production-impacting changes.

These are not full incident diaries. They are structured completion records for governed fixes.

Use a change record when a production issue required one or more of:

- source fix
- rebuilt gateway image
- prod digest promotion
- Argo rollout
- host/runtime drift repair

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

Examples:

- `2026-04-03-telegram-runtime-contract.md`
- `2026-04-03-security-architecture-workspace-governance.md`
- `2026-04-03-ollama-portproxy-drift.md`

## Rules

- Keep records short and factual.
- Link to the owning repos and runbooks instead of duplicating long explanations.
- Separate source/artifact fixes from host/runtime drift fixes.
- If a live-only emergency repair happened first, record both:
  - the emergency action
  - the governed follow-up that made it durable

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
