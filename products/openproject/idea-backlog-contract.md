# Idea Backlog Contract

## Purpose

Define the canonical OpenProject project model for captured ideas and proposals
that originate from operator workflows and later flow through
`operator-orchestration-service`.

OpenProject is the canonical backlog store for these proposal records. Git
remains the place for accepted design, implementation, and governed change
artifacts. Execution tracking for consumed accepted ideas belongs in the
separate delivery ART project defined in `delivery-art-contract.md`.

## Canonical Project

Phase 1 should use a dedicated OpenProject project:

- display name: `Workspace Proposals`
- identifier: `workspace-proposals`

This project is intended to hold:

- raw captured ideas
- triaged proposals
- parked or deferred architecture items
- accepted proposals that have not yet been promoted into Git-owned artifacts
- current `dev-integration` profile requests while OpenProject remains the
  active request surface adapter

It should not be used for:

- source change records
- execution tracking for consumed delivery work
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
  - operator-authored or operator-accepted framing exists and the next decision
    is easier to make
- `parked`
  - worth keeping, not ready for active work
- `owner-assigned`
  - clear owning repo or product has been identified
- `accepted`
  - ready to be consumed into a concrete delivery artifact such as the delivery
    ART project and later promoted into Git-owned implementation artifacts
- `rejected`
  - explicitly not proceeding
- `implemented`
  - outcome already realized elsewhere
- `superseded`
  - replaced by a newer item or better framing

Terminal statuses are future archive candidates. `archive` remains reserved as
a later visibility flag, not a lifecycle stage.

## Required Record Fields

The canonical backlog record must express at least:

- title
- description or body
- source surface
- source reference
- delivery ref when the accepted proposal has already been consumed into the
  delivery ART
- suspected owner
- affected scope
- workflow status
- triage summary
- internal evaluation notes
- optional AI-assist decision metadata when a future AI discussion path is used
- optional archival metadata when a future visibility-only archive flag is used

## Proposal-To-Delivery Handoff

`Workspace Proposals` is the intake plane, not the execution plane.

Rules:

- an accepted proposal remains the proposal-of-record
- it should be consumed into the separate delivery ART project through an
  explicit promotion step
- the proposal record should retain a durable backlink such as `delivery_ref`
- the delivery record should retain a durable backlink such as
  `origin_idea_ref`
- source proposal lifecycle must not be replaced with delivery execution status

## Production Activation Hygiene

If this two-plane model is later activated in a real `prod` environment, the
proposal plane must be noise-free and provenance-safe.

That means:

- no dev-integration smoke records
- no governed stage rehearsal records
- no placeholder or manually fabricated test proposals
- no rehearsal-only `Delivery Ref` values carried forward as production data

Allowed existing production-plane history:

- real production proposals already created there
- vetted historical imports with explicit provenance
- an explicitly approved promoted proposal-plane baseline, including the
  current validated ART/proposal history when it is being carried into
  production deliberately

Smoke, demo, and rehearsal-only data are not acceptable seed sets.

## Dev-Integration Profile Requests

The `dev-integration` profile admission model is owned generically in
`workspace-governance`.

While OpenProject is the current request surface adapter, a new profile request
may be recorded in `Workspace Proposals` before the profile becomes
`active`.

Recommended minimum mapping for that request:

- type:
  - `Component Proposal` when the profile is clearly owned by one component repo
  - otherwise the proposal type that best fits the real owner shape
- status:
  - `captured` or `triaged` while the profile is still `proposed`
- description:
  - purpose
  - participating repos
  - expected runtime dependencies
  - whether identity, secrets, runtime privilege, or AI review is involved
- custom fields:
  - `Suspected Owner`
  - `Affected Scope`
  - `Trust Boundary Areas`
  - `Promotion Target`

The generic workspace contract should then store only:

- `request_record.system`
- `request_record.ref`

That keeps the admission model portable if the request surface changes later.

## Required Custom Fields

Phase 1 should provision these custom fields in OpenProject:

- `Source Surface`
  - example: `telegram`
- `Source Reference`
  - canonical source ref such as chat/topic/message tuple
- `Delivery Ref`
  - durable backlink to the consumed delivery record when one exists
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
5. internal evaluation

This keeps the record readable to humans even if custom fields are later
changed.

## Reserved Archive Placeholder

Archive is reserved as a future visibility flag only.

Reserved metadata keys:

- `archived`
- `archived_at`
- `archived_reason`

Rules:

- archive is not a canonical status and must not replace lifecycle state
- only terminal records are future archive candidates:
  - `rejected`
  - `implemented`
  - `superseded`
- non-terminal records are not future archive candidates:
  - `captured`
  - `triaged`
  - `parked`
  - `owner-assigned`
  - `accepted`
- Phase 1 does not provision archive fields, broker behavior, or list filters
  yet

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

- update the triage summary
- set status `triaged`
- set `AI Assist Lane` to `none` for the current operator-authored phone-friendly
  path
- record `Triage Decision ID` and `Triage Confidence` only when a future
  AI-assisted discussion path is actually used

### Decision

`decision` should:

- update the operator decision notes section on the canonical work package
- set status to one of the current bounded durable outcomes:
  - `parked`
  - `accepted`
  - `rejected`
- preserve the captured idea and triage summary sections
- defer `owner-assigned` until the broker carries an explicit owner vocabulary
- record `Triage Decision ID` only when a future AI-assisted discussion path
  actually produces that metadata

### Internal Evaluation Metadata

`evaluation` should:

- update `Suspected Owner` using canonical workspace tokens only
- update `Affected Scope` using canonical workspace tokens only
- update `Trust Boundary Areas`, `Triage Confidence`, and `AI Assist Lane`
- preserve a free-text internal evaluation note in the description so the later
  full AI write-up remains readable from Telegram and OpenProject
- not change lifecycle status by itself

## Deferred In Phase 1

- OpenProject webhooks back into Telegram
- attachment mirroring
- automatic Git artifact creation
- archive visibility flag and archive-aware list behavior
- bidirectional sync with workspace contracts
