# Source Repo Contracts

## Purpose

This standard defines what the platform expects from source repositories before
their outputs are approved for `stage` or `prod`.

It exists to keep repo ownership, workflow, and evidence consistent across the
workspace.

## Core Rule

`platform-engineering` approves and records what environments run, but it does
not invent missing source contracts on behalf of other repos.

If a source repo participates in the runtime or host stack, it should already
document:

- what it owns
- what it does not own
- how it fits into the component workflow
- which validations are meaningful
- which audit, visibility, or attestation surfaces exist

## Current Repository Contract Map

| Repo | Canonical responsibility | Consumed by platform as | Required evidence surface |
| --- | --- | --- | --- |
| `openclaw-telegram-enhanced` | Telegram behavior, delivery, approvals, channel-specific UX | source SHA in `versions.yaml` and functional stage verification | tests, package metadata, gateway logs, real Telegram checks |
| `openclaw-host-bridge` | host policy enforcement, host-side health, audit, attestation, WSL runtime behavior | source SHA in `versions.yaml` plus host provisioning/runtime expectations | bridge `/healthz`, status script, journal, audit logs |
| `openclaw-runtime-distribution` | active gateway composition and bundled runtime validation | current governed build input and image assembly path | verifier scripts, build checklist, packaging path, resulting digest |
| `security-architecture` | security standards and review criteria | control expectations, not artifact input | standards, ADRs, findings, review outputs |

## Minimum Repo Documentation Contract

Every active repo should keep at least:

1. a README that states:
   - ownership
   - non-ownership
   - workflow role
   - key visibility surfaces
   - primary validation commands
2. one architecture or operating-model document
3. one operator-facing or maintainer-facing workflow document when the repo owns
   a non-trivial lifecycle

Platform-side product architecture should live under
`platform-engineering/products/<product>/`, and security architecture should
live under `security-architecture/`, instead of depending on a separate
reference repo.

## Minimum Runtime Contract For Platform Consumption

Before the platform approves a repo output, the repo should make it possible to
answer:

- what version or commit is being consumed
- what tests or verifiers cover the change
- what health or runtime signals exist
- what logs or audit trail exist
- what manual functional check is still required

## Platform Consumption Rules

- The platform pins released versions from canonical repos.
- It must not silently absorb unreleased local workspace changes.
- If a repo is reference-only, the platform should not point live environment
  contracts at it by accident.
- When a repo owner changes, the README and platform standards should be updated
  in the same change class.

## Emergency Hotfix Rule

If a live hotfix happens:

1. record the incident or containment
2. backport it to the canonical owner repo
3. rebuild or reprovision the governed path as required
4. update the platform manifest or provisioning path
5. verify drift returns to governed state
6. update the relevant docs if the incident changed the operating model

## Escalation Rule

If a repo cannot clearly answer ownership, workflow, or visibility questions,
that is a governance gap. Fix the docs or standards before expanding the repo’s
runtime responsibility further.
