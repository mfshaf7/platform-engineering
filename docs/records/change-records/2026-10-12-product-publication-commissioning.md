# Product Publication Commissioning

## Summary

Platform composes and proves the exact Product Publication path approved by
Security for Delivery ART work item `#1258`. The change reuses the existing
Console cross-domain services, OOS, WGCF, and private session boundary.

## Classification

- work home: Workspace Delivery ART `openproject://work_packages/1258`
- Landing Unit: `delivery-894-product-publication-activation`
- owner repo: `platform-engineering`
- runtime lane: local `dev-integration`
- rollout posture: internal-only, loopback-only, single-operator, synthetic data

## Exact Inputs

- Workspace Governance: `213b9fed48f8bd0e6e6fd658bfeae38cfd9e3784`
- WGCF activated source plus PostgreSQL migration repair: `556997107497ce1ae6ad8635c96591e186bca629`
- OOS activated source: `e10a3265b6ca3e9ca16d74f453fe7b6285d5d5b1`
- Console manifest revision: `83b0e20786bd6cd531e1043acf96df60ee5a3555`
- Console owner source: `9ef4e2f370439464afb0284131446d34abf4aa6d`
- manifest digest: `sha256:86f714e45ff092618558eb5649c9daa496e3f77e27ff3e90eafffc267650102f`
- Security decision: `security-architecture://product-publication/decisions/console-internal-v1`
- Security revision: `3dc6e0f6cc2f829b4967ac73269a409e18e0de21`
- Security digest: `sha256:d1d120e1a081d29319394f70fc31b423f81039ccef9e2da0b87327241f5ba837`

## Ownership

- Workspace Governance owns policy and product identity.
- WGCF owns readiness and immutable readiness evidence.
- OOS owns workflow state and the terminal owner receipt.
- Console owns reviewed intent submission and result projection.
- Security Architecture owns acceptance.
- Platform owns runtime composition, proof, rollback, and teardown.

## Root Cause

The source implementations and Security decision were complete, but the local
runtime did not yet project the exact OOS, WGCF, owner-source, session, and
Console integrity bindings required to activate the path.

## Source Changes

This Landing Unit adds one bounded policy, one product-qualified operator
command, tests, evidence-profile coverage, and the primary runbook. It extends
the existing composition and creates no new control plane.

## Artifact And Deployment Evidence

The final record will bind the reviewed Platform commit and the existing exact
OOS, WGCF, Console, Workspace Governance, owner-manifest, architecture, and
Security revisions. Runtime receipts remain operator-private and contain no
credentials.

## Controls And Evidence

The Platform policy and command reject source, manifest, architecture,
Security, target, operator, or runtime drift. Credentials remain in the
existing private runtime projections and Kubernetes Secret references. The
browser receives none of them.

Commissioning proves one internal publication, readiness and owner-receipt
readback, unauthorized caller denial, Security mismatch denial, stale manifest
denial, replay conflict denial, broader-posture denial, restart-safe replay,
bounded rollback and teardown, final restoration, and exact durable readback.

## Live Verification

`make governance-console-product-publication ACTION=commission` is the bounded
live sequence. `ACTION=verify-operating` is the non-mutating evidence-profile
entry point after commissioning and requires the same Platform source revision.

## Rollback

Remove only the four Console integrity-metadata variables, OOS Product
Publication variables and state mount, and WGCF Product Publication variables
and read-only owner mount. Preserve OOS journal state, WGCF ledger evidence,
source, Security decisions, Git history, and Platform receipts. Source-level
revocation remains a separately reviewed owner-repository change.

## Follow-Up Actions

No broader publication posture or environment is implied. Any expansion needs
new Workspace Governance, owner-source, Security, and Platform decisions.
