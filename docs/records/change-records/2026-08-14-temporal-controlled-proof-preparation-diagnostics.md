# Temporal Controlled-Proof Preparation Diagnostics

## Summary

- Date: 2026-08-14
- Short title: Retain actionable preparation-failure diagnostics
- Environment: `dev-integration`
- Severity: commissioning blocker

## Classification

- Type: app source bug
- User-facing impact: ART #751 spent its valid single-use v3 authorization,
  but scenarios 1-10 could not run and the retained evidence could not identify
  which permit-bound preparation phase failed.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`,
  `workspace-governance-control-fabric`
- Related ADR:
  [ADR-018](../../decisions/adr/ADR-018-permit-gated-component-commissioning-proof.md)

## Root Cause

- Immediate failure: the permit-bound `prepare` command returned nonzero; the
  terminal result recorded scenarios 1-10 as `not-run` with
  `preparation-failed`.
- Actual root cause: command-failure evidence retained only executable,
  return code, output digests, and byte counts. Exact-baseline cleanup removed
  the scoped namespace before the failed preparation phase could be identified.
- Why it escaped earlier controls: the existing positive test proved that raw
  output was excluded, but did not require a safe semantic diagnostic from the
  trusted runtime script.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): this ART #840 landing unit; the finalized Review Packet records
  the exact merged commit.
- Guardrail added:
  - emit one fixed action, phase, and exit-code marker from the permit-bound
    runtime script
  - accept only known actions and phases whose exit code matches the sandbox
    command result
  - retain raw output only as digests and byte counts
  - test accepted and rejected diagnostic markers plus direct-invocation denial
  - document the bounded diagnostic contract in the primary operations guide

## Artifact And Deployment Evidence

- Build workflow run: pending source landing
- Published image tag: None; Platform executor source only
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: None; v3 exact-baseline restoration passed.
- Why it was environment drift instead of source defect: None; diagnostic
  custody was a source defect.
- Recovery command or procedure: merge ART #840, issue a fresh authorization,
  and run a new commissioning session. The v3 permit remains consumed.

## Live Verification

- App health: v3 ended `failed` with all operator-scoped runtime surfaces
  restored to `not-installed`.
- Deployed image: no proof image remains active.
- Pod: no proof Pod remains after exact restoration.
- Functional verification: focused tests prove recognized phase retention,
  unrecognized phase rejection, raw-output exclusion, and direct invocation
  denial.
- Residual risk: the underlying preparation failure remains unclassified until
  a fresh session produces the new semantic diagnostic.

## Follow-Up

- Required follow-up: merge ART #840 and rerun ART #751 only with a fresh
  permit.
- Optional hardening: None before the fresh run; classify its bounded evidence
  before expanding the diagnostic vocabulary.
- Owner: Platform Engineering
