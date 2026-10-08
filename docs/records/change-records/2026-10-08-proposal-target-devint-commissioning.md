---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# Proposal Target Dev-Integration Commissioning

## Summary

- Date: 2026-10-08
- Short title: Commission Proposal Target runtime availability
- Environment: `dev-integration`
- Severity: Planned capability activation, not an incident

## Classification

Delivery ART `#1236` under Feature `#1212` and Epic `#1203`; source Landing
Unit `delivery-1203-proposal-target-platform`. Identity creation, runtime
projection, loopback composition, operating proof, rollback, and recovery are
parts of this existing Landing Unit and do not create another ART child.

## Ownership

Platform owns the dedicated GitHub App contract, private-key custody,
short-lived token delivery, OOS runtime projection, Console loopback
composition, rollback, and recovery. OOS owns durable application progression
and Proposal acknowledgement. Prototype Studio owns target mutation and its
receipt. The human reviewer owns exact-head approval and merge. Security work
item `#1235` owns the accepted trust boundary.

## Root Cause

The OOS capability was source-activated, but Platform had not yet defined or
delivered the dedicated provider identity, composed the exact source revisions,
or proven the live Console-to-OOS-to-Studio path. Reusing an existing identity
would have crossed an unrelated workflow's branch, path, audit, and revocation
boundary.

## Source Changes

Platform defines a dedicated exact-repository Proposal Target identity rather
than reusing Prototype Landing, Maturity, Closure, Agent Gary, or ambient human
credentials. The shared Prototype workflow operator now supports identities
that do not require WGCF bindings, while existing WGCF-backed workflows retain
their original behavior and tests. The Proposal Target entrypoint projects
only its short-lived token, persistent state, and read-only Prototype Studio
source into the admitted OOS session.

The Console commissioning policy pins the activated OOS source, exact Console,
Prototype Studio, Security, WGCF, Workspace Governance, and architecture
inputs. It reuses the managed loopback services and private server-side Console
credential boundary. The primary runbook defines positive completion,
negative denials, restart, rollback, cleanup, and clean redelivery without
placing a provider token in Console or the browser.

The first live dispatch exposed that the Console adapter serialized the local
human session principal where OOS requires its authenticated machine caller.
Console pull request `#53` restored that reviewed attribution boundary, and
Security Architecture pull request `#204` re-accepted the exact repaired
revision. This Platform pin refresh admits only those merged revisions; it does
not expand the Proposal Target identity or exposure model.

The resumed live proof then exposed a second adapter mismatch: Console supplied
a Prototype id that the OOS preparation contract intentionally derives itself.
Console pull request `#54` removed that extra field and added exact request-body
coverage; Security Architecture pull request `#205` re-accepted the narrower
request at its merged revision.

The next live step exposed the matching submission-side mismatch: Console
included free-form Prototype suggestion fields although OOS accepts only the
derived Prototype identity. Console pull request `#56` removed those fields
and made the exact Prototype binding part of conformance coverage; Security
Architecture pull request `#206` re-accepted the narrower submission at its
merged revision.

The repaired request then reached Studio and exposed an older synthetic
handoff-reference contract: the target path accepted `proposal-packet:<id>`
but the canonical accepted-Proposal workflow emits
`proposal-handoff:idea-<id>:version-<version>`. Prototype Studio pull request
`#24` admitted both bounded forms while preserving exact Proposal, Prototype,
and handoff identity checks. OOS pull request `#288` synchronized that contract,
Console pull request `#57` synchronized its conformance fixture, and Security
Architecture pull request `#207` re-accepted the exact repaired chain. This is
an owner-maintenance repair within `#1236`, not a new ART work item.

The Platform evidence profile now binds Repository/Catalog and Proposal Target
live checks to their exact operating conformance cases. Its Proposal Target
verifier is non-mutating: a separate commissioning command first validates the
completed OOS application, human-reviewed Studio merge, canonical Proposal
acknowledgement, denial matrix, and ordered restart/rollback/cleanup/redelivery
receipts. This consumes the merged OOS case-binding maintenance control and
prevents another same-fidelity capability from running during `#1236`.

## Required Operating Evidence

The final value-free evidence must prove the exact App, installation,
repository, permissions, source revisions, current OOS session, read-only
mounts, persistent state, positive human-reviewed merge and canonical
readback, negative denial cases, restart recovery, revocation, cleanup, and
fresh final delivery. No private key, installation token, Console/OOS secret,
authorization header, or public-source-unsafe Proposal content may appear in
source, logs, receipts, or ART evidence.

## Artifact And Deployment Evidence

Pending the reviewed Platform merge and value-free live evidence attachment for
`#1236`. Source validation alone is not deployment or operating evidence.

## Live Verification

Pending dedicated App commissioning and the positive, negative, restart,
rollback, cleanup, and final-redelivery sequence in the primary runbook. Until
that proof exists, this record does not claim normal availability.

## Rollback

Suspend new Proposal Target work, revoke the projected token, remove only its
Secret, environment, and mounts, and stop the managed loopback services.
Retain source, canonical Git history, merged target records, Proposal
acknowledgement, durable OOS state, review history, and value-free evidence.
Restore availability only with a new exact-repository token and current source
readback.

## Follow-Up Actions

Complete the `#1236` live proof, replace these pending statements with exact
receipt and revision references, merge the Platform Landing Unit, and bind its
final Review Packet before Feature `#1212` or Epic `#1203` closes.
