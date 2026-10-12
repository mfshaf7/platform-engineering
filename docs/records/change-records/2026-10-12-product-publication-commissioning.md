# Product Publication Commissioning

## Summary

Platform composes and proves the exact Product Publication path approved by
Security. Delivery ART work item `#1258` established the internal-only path;
`#1264` recommissions that same composition against the audience decision
without widening its target set. The change reuses the existing Console
cross-domain services, OOS, WGCF, and private session boundary.

## Classification

- work home: Workspace Delivery ART `openproject://work_packages/1264`
- Landing Unit: `delivery-894-audience-platform`
- owner repo: `platform-engineering`
- runtime lane: local `dev-integration`
- rollout posture: internal-only, loopback-only, single-operator, synthetic data

## Exact Inputs

- Workspace Governance Security-reviewed contract source: `213b9fed48f8bd0e6e6fd658bfeae38cfd9e3784`
- Workspace Governance exact runtime authority descendant: `ade4549746bc6e727e97397be7b0c89758677a0c`
- WGCF Security-reviewed readiness source: `d12545242fed839df3bce65ad4dd5d6482e7854a`
- WGCF exact runtime activation descendant: `8cc666efbb4bb6c582571c438a3a8fa5c8342cdb`
- OOS Security-reviewed audience source: `a5c5fd5a8adc93b79e82d93abced31b65f055cd4`
- OOS Security-bound activation: `a690e25b902c248b43f055a69f1b5e6647c01d3e`
- Console audience projection: `79f95608c71fd4d74244e89324c6c5d45cd416f7`
- Console Security-reviewed manifest revision: `83b0e20786bd6cd531e1043acf96df60ee5a3555`
- Console exact runtime manifest descendant: `79f95608c71fd4d74244e89324c6c5d45cd416f7`
- Console owner source: `9ef4e2f370439464afb0284131446d34abf4aa6d`
- manifest file digest: `sha256:86f714e45ff092618558eb5649c9daa496e3f77e27ff3e90eafffc267650102f`
- manifest canonical digest used by the workflow: `sha256:e042aae5afc266cf23f02de747ee773561efb9541747ca14a94c0f35c614015e`
- Security decision: `security-architecture://product-publication/decisions/audience-internal-only-v1`
- Security revision: `9729514bd764fad8700a649035f860fa1e0a97d4`
- Security decision digest: `sha256:9a3ca8531c686fe9c278d82e7328099517e56de4fc856f33c177d9de2ed44494`
- current corrected architecture: `wgcf://artifacts/delivery-art/sha256/c04c3242a7ddb6f6b1de9b9ea3fc1bbd6c2830f68fa6665a45aaba416dcbf422`
- Security-reviewed architecture anchor: `wgcf://artifacts/delivery-art/sha256/f31cf6c0a0d015345a0b286bf334719731e398337941591fb6c6143a2ef238ff`

## Ownership

- Workspace Governance owns policy and product identity.
- WGCF owns readiness and immutable readiness evidence.
- OOS owns workflow state and the terminal owner receipt.
- Console owns reviewed intent submission and result projection.
- Security Architecture owns acceptance.
- Platform owns runtime composition, proof, rollback, and teardown.

## Root Cause

The original internal-only composition was commissioned, but it did not bind
the later audience Security decision, OOS activation revision, Console audience
projection, complete four-target denial matrix, or process-loss recovery case.
The accepted #1258 receipt already records `internal` at version 1 while the
owner manifest intentionally remains `unlisted`; issuing another initial
publication would contradict both durable facts. #1264 therefore proves exact
continuity of that receipt under the new enforcement source instead of
duplicating or rewriting the publication.

## Source Changes

This Landing Unit refreshes one bounded policy and its existing
product-qualified operator command, tests, evidence-profile coverage, change
record, and primary runbook. It extends no control plane and grants no product
access.

## Artifact And Deployment Evidence

The final record will bind the reviewed Platform commit and the existing exact
OOS, WGCF, Console, Workspace Governance, owner-manifest, architecture, and
Security revisions. Runtime receipts remain operator-private and contain no
credentials.

## Controls And Evidence

The Platform policy distinguishes Security-reviewed capability, authority, and
manifest revisions from their exact activated runtime descendants. It proves
each ancestry relation, requires the reviewed Workspace Governance contract
and owner-manifest bytes to remain unchanged, and rejects source, manifest,
architecture, Security, target, operator, or runtime drift. This avoids
treating inactive or superseded reviewed commits as runnable heads while
preserving their exact Security-review lineage.
Credentials remain in the existing private runtime projections and Kubernetes
Secret references. The browser receives none of them.

Commissioning proves exact readback of the existing internal publication and
owner receipt without a second mutation, unauthorized caller denial, Security mismatch denial, stale manifest
denial, replay conflict denial, separate `unlisted`, `client`, `public`, and
`archived` target denial, OOS process-loss failure without false state,
restart-safe replay, bounded rollback and teardown, final restoration, and
exact durable readback.

## Live Verification

`make governance-console-product-publication ACTION=commission` is the bounded
live sequence. `ACTION=verify-operating` and
`ACTION=verify-process-crash` are the non-mutating evidence-profile entry
points after commissioning and require the same Platform source revision.

## Rollback

Remove only the four Console integrity-metadata variables, OOS Product
Publication variables and state mount, and WGCF Product Publication variables
and read-only owner mount. Preserve OOS journal state, WGCF ledger evidence,
source, Security decisions, Git history, and Platform receipts. Source-level
revocation remains a separately reviewed owner-repository change.

## Follow-Up Actions

No broader publication posture, owner access route, access grant, or
environment is implied. Any expansion needs new Workspace Governance,
owner-source, Security, and Platform decisions.
