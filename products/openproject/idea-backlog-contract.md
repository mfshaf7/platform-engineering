# Idea Backlog Contract

## Purpose

Define the canonical OpenProject project model for captured ideas and proposals
that originate from operator workflows and later flow through
`operator-orchestration-service`.

OpenProject is the canonical backlog store for these records. Git remains the
place for accepted design, implementation, and governed change artifacts.

## Canonical Project

Phase 1 should use a dedicated OpenProject project:

- display name: `Workspace Proposals`
- identifier: `workspace-proposals`

This project is intended to hold:

- raw captured ideas
- triaged proposals
- parked or deferred architecture items
- accepted proposals that have not yet been promoted into Git-owned artifacts

It should not be used for:

- source change records
- release approval or promotion state
- platform runtime evidence

## Ownership

- OpenProject runtime owner: `platform-engineering`
- backlog semantics owner: `workspace-governance`
- workflow caller: `operator-orchestration-service`
- security owner: `security-architecture`

## Work Package Types

Phase 1 should support these types:

- `Idea`
  - default type for newly captured items
- `Governance Proposal`
- `Security Proposal`
- `Product Proposal`
- `Component Proposal`

Broker rule:

- `capture` creates an `Idea`
- later operator-approved triage may keep it as `Idea` or retarget it to a more
  specific proposal type

## Status Model

Phase 1 canonical statuses:

- `captured`
- `triaged`
- `parked`
- `owner-assigned`
- `accepted`
- `rejected`
- `implemented`
- `superseded`

Status meaning:

- `captured`
  - raw record exists but no approved triage yet
- `triaged`
  - bounded suggestion accepted by an operator
- `parked`
  - worth keeping, not ready for active work
- `owner-assigned`
  - clear owning repo or product has been identified
- `accepted`
  - ready to promote into a concrete Git or delivery artifact
- `rejected`
  - explicitly not proceeding
- `implemented`
  - outcome already realized elsewhere
- `superseded`
  - replaced by a newer item or better framing

## Required Record Fields

The canonical backlog record must express at least:

- title
- description or body
- source surface
- source reference
- suspected owner
- affected scope
- workflow status
- triage decision id
- triage confidence

## Required Custom Fields

Phase 1 should provision these custom fields in OpenProject:

- `Source Surface`
  - example: `telegram`
- `Source Reference`
  - canonical source ref such as chat/topic/message tuple
- `Suspected Owner`
  - repo or product owner guess
- `Affected Scope`
  - repos, products, or components touched by the idea
- `Trust Boundary Areas`
  - identity, secrets, delivery, runtime, ai
- `Promotion Target`
  - where accepted items should move next
- `Triage Decision ID`
  - broker decision correlation id
- `Triage Confidence`
  - low, medium, high
- `AI Assist Lane`
  - none, local, governed, exception
- `Revisit On`
  - date for parked or deferred items

Field ids may vary by instance, but the semantic names above are the contract.

## Current Live Mapping

As of `2026-04-18`, the current local platform OpenProject runtime reports:

- type ids:
  - `Idea`: `41`
  - `Governance Proposal`: `42`
  - `Security Proposal`: `43`
  - `Product Proposal`: `44`
  - `Component Proposal`: `45`
- status ids:
  - `captured`: `81`
  - `triaged`: `82`
  - `parked`: `83`
  - `owner-assigned`: `84`
  - `accepted`: `85`
  - `rejected`: `80`
  - `implemented`: `86`
  - `superseded`: `87`
- custom field ids:
  - `Source Surface`: `1`
  - `Source Reference`: `2`
  - `Suspected Owner`: `3`
  - `Affected Scope`: `4`
  - `Trust Boundary Areas`: `5`
  - `Promotion Target`: `6`
  - `Triage Decision ID`: `7`
  - `Triage Confidence`: `8`
  - `AI Assist Lane`: `9`
  - `Revisit On`: `10`

These ids are instance-local runtime facts, not the semantic contract. If the
OpenProject backlog model is reprovisioned in a new instance, operators should
re-read the live ids before wiring or repairing broker runtime env values.

## Description Structure

In addition to custom fields, the work package description should preserve these
sections in a stable order:

1. captured idea
2. discussion excerpt or source context
3. triage summary
4. operator decision notes

This keeps the record readable to humans even if custom fields are later
changed.

## Automation Identity

The broker must not use a personal operator account.

Phase 1 recommendation:

- dedicated OpenProject automation user:
  - `operator-orchestration-service`
- authentication method:
  - single-purpose API token

The API token should be created specifically for this workflow and not reused by
other applications.

## Automation Permissions

The automation identity should have only the minimum access required for the
`workspace-proposals` project:

- project roles:
  - `Reader`
  - `Work package creator`
  - `Work package editor`

These roles together provide:

- view project
- view work packages
- create work packages
- edit work packages
- add notes or comments if needed for decision history

It should not have:

- global admin
- user administration
- project administration outside the dedicated backlog project

## Secret And Config Shape

When the broker becomes active, split config into:

Secret:

- Vault path:
  - `kv/components/operator-orchestration-service/prod/openproject`
- expected secret:
  - `apiToken`

This secret belongs to the broker component, not to the OpenProject runtime
namespace secret tree.

Non-secret config:

- OpenProject base URL
- OpenProject host header when the runtime enforces a canonical external host
- project identifier `workspace-proposals`
- type mapping
- status mapping
- custom-field mapping

## Broker Mapping Rules

### Capture

`capture` should:

- create or reuse a work package of type `Idea`
- set status `captured`
- fill title, description, source surface, source reference

### Triage

`triage` should:

- update triage summary and suggestion metadata
- set `Triage Decision ID`
- set `Triage Confidence`
- set `AI Assist Lane`
- leave final durable status unchanged until operator decision

### Decision

`decision` should:

- update the canonical work package with the accepted or overridden outcome
- set status according to the operator action
- preserve the decision id tied to that accepted outcome

## Deferred In Phase 1

- OpenProject webhooks back into Telegram
- attachment mirroring
- automatic Git artifact creation
- bidirectional sync with workspace contracts
