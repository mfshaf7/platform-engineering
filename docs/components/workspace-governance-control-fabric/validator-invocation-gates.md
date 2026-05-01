# WGCF Validator Invocation Gates

## Purpose

This document defines the platform gate for using
`workspace-governance-control-fabric` to invoke governance validators and store
their receipts.

Authoritative platform decision:

- [ADR-016: WGCF Validator Invocation Profile Gates](../../decisions/adr/ADR-016-wgcf-validator-invocation-profile-gates.md)

It covers platform execution posture only. It does not move workspace contract
authority, security acceptance, platform release approval, or Delivery ART
mutation into WGCF.

## Authority Boundary

WGCF may plan, run, cache, and receipt validator checks only when the requested
command is admitted by the workspace validator catalog and the platform profile
for that invocation is approved.

WGCF must not:

- mutate Delivery ART state
- mutate workspace-governance contracts, repo rules, skills, or generated truth
- approve platform stage or prod release
- accept security risk
- treat a compact receipt as a substitute for a full artifact when the gate
  requires full custody

## Profile Gates

| Profile | Allowed Use | Required Before Use | Denied Behavior |
| --- | --- | --- | --- |
| `devint-shadow` | Local-k3s or local-source shadow comparison between direct validators and WGCF receipts. | Active `governance-control-fabric` dev-integration profile, workspace validator catalog entry, read-only or explicitly approved command class, receipt output budget. | No stage/prod claims, no authority mutation, no direct ART mutation, no raw artifact projection to models. |
| `stage-readiness` | Governed rehearsal of validator invocation for a release candidate. | Reviewed source revision, platform release candidate record, service identity plan, secret-delivery plan, PostgreSQL migration/rollback plan, security delta review, observability and backup/restore plan. | No prod use, no raw artifact custody without approved object-store and retention controls, no replacement of direct validators until shadow parity passes. |
| `prod-readiness` | Normal production validation invocation after stage evidence is accepted. | Clean stage-readiness evidence, approved image or package pin, support-readiness record, rollback/suspension procedure, retention policy, restore evidence, security acceptance posture. | No break-glass behavior as default, no unbounded output capture, no execution outside admitted catalog/profile scope. |
| `break-glass` | Time-bounded diagnostic invocation for an active incident or blocked release. | Explicit operator approval, reason, target scope, expiry, caller identity, direct rollback path, receipt and ledger entry. | No silent default use, no broad recursive validation, no suppression of denied or redacted evidence. |

## Persistence And Retention Posture

Current `devint-shadow` state is local evidence only:

- PostgreSQL data lives in the local dev-integration namespace and PVC.
- `devint-down` preserves persistent profile data.
- `devint-reset` is the destructive path and may remove local profile history.
- Local receipts are evidence for iteration, not governed stage/prod evidence.

Before `stage-readiness` or `prod-readiness`, the platform must define:

- PostgreSQL ownership, migrations, backup, restore, and rollback
- receipt metadata retention
- ledger retention
- cleanup behavior for expired receipts and suppressed artifacts
- object-store custody for redacted and raw artifacts, if full artifact
  preservation is approved
- access controls for artifact lookup and receipt query
- deletion and restore expectations for evidence stores

Default artifact posture:

- compact receipts are allowed when they avoid raw operational output
- raw artifacts are denied by default outside local custody
- redacted artifacts require retention and access policy before governed use
- raw artifact storage requires a fresh approved custody gate before activation

## Observability Gate

WGCF observability must integrate with the existing platform observability
model.

Required platform-visible signals before governed use:

- validator invocation count by profile and safety class
- selected, suppressed, blocked, stale, and waived check counts
- receipt generation success and failure counts
- output budget used and truncation count
- redaction or suppression count
- artifact custody denied count
- stale authority snapshot count
- dependency failure count for PostgreSQL, policy evaluation, and object store
  when those dependencies are active

Prometheus is the current metrics surface. OpenTelemetry-compatible trace and
correlation fields may be added later to connect operator actions, validation
runs, receipts, and ledger events, but OpenTelemetry must not replace the
existing Prometheus-based platform health model.

Logs must not include raw validator output, secrets, raw environment dumps, or
full artifact payloads.

## Cutover Requirements

Workspace-governance may treat WGCF as a normal validator invocation path only
after all applicable gates are true:

- the command exists in the workspace validator catalog
- the command safety class is allowed by the selected profile
- the platform profile gate is satisfied
- security-architecture has a current delta review for the invocation and
  artifact-custody boundary
- shadow parity demonstrates equivalent pass/fail posture and receipt evidence
- the direct validator remains available as rollback
- receipt output is compact, bounded, and linked to artifact references rather
  than raw dumps

Direct validators remain the compatibility path until the workspace
shadow-parity contract explicitly marks a scope retirement-eligible.
