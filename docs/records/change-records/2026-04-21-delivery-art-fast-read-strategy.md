---
security_evidence:
  review_areas:
    - runtime
  findings:
    - F-000
  risks:
    - R-000
  workstreams:
    - WS-000
---

# Delivery ART Fast Read Strategy

## Summary

- Date:
  - 2026-04-21
- Short title:
  - Delivery ART fast read strategy
- Environment:
  - local dev-integration and operator documentation surfaces
- Severity:
  - medium operator-latency defect

## Classification

- Type:
  - app/plugin source bug
- User-facing impact:
  - routine ART startup reads were slow enough to encourage bypassing the
    governed read path

## Ownership

- Owning repo or layer:
  - `platform-engineering/products/openproject`
- Related repos:
  - `workspace-governance`
- Related ADR:
  - None

## Root Cause

- Immediate failure:
  - the session-start doctrine pushed every routine delivery turn through the
    heaviest OpenProject read surfaces
- Actual root cause:
  - there was no tiered read model distinguishing a fast active-front read from
    the deeper evidence-grade execution and portfolio reads
- Why it escaped earlier controls:
  - ART-quality and initiative-summary controls were treated as startup defaults
    instead of deliberate deeper checks

## Source Changes

- Repo:
  - `platform-engineering`
- Commit(s):
  - local change only at record time
- Guardrail added:
  - runbook

## Artifact And Deployment Evidence

- Build workflow run:
  - None
- Published image tag:
  - None
- Published digest:
  - None
- Recorded prod revision:
  - None
- Argo application revision:
  - None

## Host Or Runtime Recovery

- Required host/runtime action:
  - None
- Why it was environment drift instead of source defect:
  - it was a source and operator-workflow issue, not host drift
- Recovery command or procedure:
  - `make openproject-show-delivery-active-front TARGET_EPIC_ID=<epic-id>`

## Live Verification

- App health:
  - `devint-accepted-idea-delivery-mfshaf7` remained healthy during the new
    fast-read proof
- Deployed image:
  - None
- Pod:
  - broker deployment inside `devint-accepted-idea-delivery-mfshaf7`
- Functional verification:
  - the new fast active-front read returned the committed front for `Epic #38`
    from the live devint ART
  - the scoped ART-quality check for `TARGET_EPIC_ID=38` returned
    `issue_count: 0`
- Residual risk:
  - the deeper portfolio initiative summary is still the slower read and should
    remain a deliberate replanning/governance surface rather than a default
    startup path

## Follow-Up

- Required follow-up:
  - none beyond landing the updated runbooks and skill guidance
- Optional hardening:
  - brokerize the portfolio initiative summary later if portfolio-level reads
    become routine operator work
- Owner:
  - `platform-engineering`
