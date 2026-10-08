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

That repair changed Studio `main` while the retained live application was
still bound to the earlier target revision. OOS correctly rejected both a
conflicting resubmission and an authority-stale continuation, but cancellation
left no bounded restart for a record that had created no files, review, target
result, Proposal acknowledgement, or canonical mutation. OOS pull request
`#289` added only that explicit cancel-and-restart path with independent
service and durable-store enforcement; Security Architecture pull request
`#208` accepted the exact merged control. All other conflicting replays remain
denied.

The Platform evidence profile now binds Repository/Catalog and Proposal Target
live checks to their exact operating conformance cases. Its Proposal Target
verifier is non-mutating: a separate commissioning command first validates the
completed OOS application, human-reviewed Studio merge, canonical Proposal
acknowledgement, denial matrix, and ordered restart/rollback/cleanup/redelivery
receipts. This consumes the merged OOS case-binding maintenance control and
prevents another same-fidelity capability from running during `#1236`.

Final commissioning exposed a receipt-time contradiction after the successful
application advanced Prototype Studio `main`: lifecycle receipts had been
issued against the policy's activation baseline, but the verifier recomputed
their Studio source from the newer live head. The repair keeps lifecycle source
evidence bound to the policy activation revision and leaves the existing
canonical target proof responsible for the current post-merge Studio revision.
This preserves both facts without weakening ancestry, exact-file, reviewed
merge, or current-authority validation.
Security Architecture pull request `#209` re-accepted that exact verifier
boundary. The commissioning policy, identity contract, and operator examples
now pin its merged decision before the final lifecycle proof is regenerated.

The original `#1236` Review Packet remained bound to Platform pull request
`#267` at source revision `5bc83a2ba54977d137f59f81b9a67931ba19cb18`.
The reviewed verifier and contract repairs landed afterward through Platform
pull requests `#274`, `#275`, and `#276`, so replaying the original
post-merge evidence against current authority correctly failed closed. OOS
pull request `#290` added the bounded recovery that archives this obsolete
operating evidence while preserving the immutable merge-ready packet. Security
Architecture pull request `#210` synchronized its generated change-record
index. The recovered `#1236` Landing Unit records the final receipts below
against current Platform source; it does not rewrite or discard the original
review evidence.

## Required Operating Evidence

The final value-free evidence must prove the exact App, installation,
repository, permissions, source revisions, current OOS session, read-only
mounts, persistent state, positive human-reviewed merge and canonical
readback, negative denial cases, restart recovery, revocation, cleanup, and
fresh final delivery. No private key, installation token, Console/OOS secret,
authorization header, or public-source-unsafe Proposal content may appear in
source, logs, receipts, or ART evidence.

## Artifact And Deployment Evidence

The source and review chain is merged and provider-confirmed:

- Platform pull request `#267`: head
  `5bc83a2ba54977d137f59f81b9a67931ba19cb18`, merge
  `e2c48122858fd0fe154ca9d7a8e11e9b56a5c61f`.
- Platform verifier repair pull request `#274`: head
  `665c380fec91e580e86bf9dabbfbcfb7a888c0ab`, merge
  `85d7287ddccf021637d36131a5b661e75f1fdf4c`.
- Platform Security-pin refresh pull request `#275`: head
  `3fcb6322ae35baa2e76ce39895ad2c403e5ad105`, merge
  `fee8885c1b5b407b54e2b5a60b11cc762f1beda4`.
- Platform cross-surface revision repair pull request `#276`: head
  `b546567882a693fc37b4734d8d86f074131261c0`, merge and
  activation revision `2c76c0df78a61ebb8cad3e64c94231ed25e157be`.
- Security acceptance pull request `#209`: merge
  `add3b405cffe87d158c65edec1d24cf33ea2def8`; generated-index
  synchronization pull request `#210`: merge
  `24fc2a6db32d2ba04ade9c3bdea7cc022153ddbc`.
- OOS evidence-recovery pull request `#290`: head
  `f483ba6f7d4cc43bde49daf3ad8b136e2a21ec13`, merge
  `c0ef285a39938050b6a7ae976f315245269ea58b`.

The final activation and status receipts are
`20261008T122258Z-activate.json`
(`sha256:557e8e95841594f1bf8d279b2f9675a9c98d1368b971290b120f46292e5e97f2`)
and `20261008T122259Z-status.json`
(`sha256:3099ed6674f38266f1ba0d75013ae7bfc9a7f2cc1f5f15637f1c9741cc9c3c32`).
Both report successful `dev-integration` operation, active managed services,
private `0600` Console environment state, preserved owner sessions, no browser
credential exposure, and the current architecture digest
`sha256:3a4b5edb6bc54ff47a45f610b41f75bc57dd9d1ab56e9475518100d75ff72ab0`.

## Live Verification

The final commissioning receipt
`20261008T122315Z-proposal-target-commission.json`
(`sha256:9ac3baac009633ec2e7c031891c7c5e75d2ab07b23e893d9b0f12ded82131e77`)
and its independent verification receipt
`20261008T122321Z-proposal-target-commission-verification.json`
(`sha256:cbb1eb98626e7c9be5c8ee1a84f3854d400765f2ebd4bce9e4e0f83ccc9eaf32`)
both succeeded.

They prove Proposal `idea-218` reached Prototype
`prototype:proposal-218` through application revision `8`; Studio pull request
`#25` was human-reviewed and merged at
`084bfe2055db8bd3d7b9dde3b06f71abe51671b3`; canonical target readback and
Proposal acknowledgement succeeded; restart recovery, rollback, cleanup, and
fresh final delivery completed; and the final availability state was restored.
The negative matrix denied invalid caller, caller-selected Prototype,
conflicting replay, stale Proposal version, changed Studio authority,
unreviewed or wrong-head source, and provider loss without changing canonical
state. The final target receipt is
`proposal-prototype-target-receipt:proposal-218:8470621ff1d0f4008959ea813d80e3b9b3a8cb6fc2d0539b74617a5f52fa2b79`.

## Rollback

Suspend new Proposal Target work, revoke the projected token, remove only its
Secret, environment, and mounts, and stop the managed loopback services.
Retain source, canonical Git history, merged target records, Proposal
acknowledgement, durable OOS state, review history, and value-free evidence.
Restore availability only with a new exact-repository token and current source
readback. Receipt `20261008T121618Z-rollback.json` proves the bounded rollback,
`20261008T121642Z-cleanup.json` proves cleanup, and the final activation and
status receipts above prove clean redelivery.

## Follow-Up Actions

Merge this recovered Platform evidence consolidation and bind its final Review
Packet to `#1236`. Feature `#1212` and Epic `#1203` may close only after that
packet, post-merge operating evidence, and their completion evidence are
accepted.
