# 2026-04-26 Delivery ART Initiative Lineage Governance

## Summary

Added first-class initiative-family and lineage governance to the canonical
OpenProject ART contract so top-level epics can be grouped, reviewed, and
validated as coherent initiative families instead of one flat portfolio.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery execution
  - portfolio governance
  - managed OpenProject views

## Ownership

- broker lineage mirror and initiative-governance surface:
  `operator-orchestration-service`
- workspace reminders, skill guidance, and cross-repo truth:
  `workspace-governance`

## Root Cause

The ART had strong planning, closeout, and blocker doctrine, but top-level
initiative lineage still depended on prose and operator memory. That let
architecture-bearing chains such as `#38 -> #227 -> #245 -> #251` drift into a
flat portfolio view where unrelated hardening epics looked adjacent without any
machine-readable family or anchor semantics.

## Source Changes

- added the canonical initiative-lineage contract:
  - `products/openproject/delivery-art-initiative-lineage.json`
- provisioned new Epic-only custom fields from that contract:
  - `products/openproject/scripts/openproject_configure_delivery_art_runner.rb`
- added managed OpenProject family queries and board projection:
  - `products/openproject/scripts/openproject_sync_delivery_art_views_runner.rb`
- added quality-gate enforcement for:
  - allowed unclassified shell posture
  - required family and lineage role outside the shell
  - anchor and upstream ref shape
  - family alignment across anchor and upstream chains
  - `products/openproject/scripts/openproject_check_delivery_art_quality.py`
- added regression coverage for the new lineage gates:
  - `products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
- documented the lineage doctrine and operator checklist:
  - `products/openproject/delivery-art-contract.md`
  - `products/openproject/runbooks/manage-delivery-initiative-lineage.md`
  - `products/openproject/runbooks/plan-delivery-art.md`
  - `products/openproject/README.md`
  - `products/openproject/AGENTS.md`
  - `products/openproject/runbooks/README.md`

## Live-State Impact

- no governed stage or prod change yet
- active delivery ART devint lane will gain lineage custom fields and managed
  initiative-family views after the configure/sync run

## Artifact And Deployment Evidence

- deployment artifact:
  - OpenProject configure and view-sync runners extended in source
- proof artifact:
  - pending live backfill and quality sweep against `workspace-delivery-art`

## Live Verification

- `python3 products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- the live ART quality sweep should fail if any top-level initiative leaves the
  allowed shell posture without lineage classification or violates anchor/gate
  family coherence

## Follow-Up

- provision the lineage fields into the active OpenProject ART
- backfill all existing top-level epics, including `#87`, into explicit
  initiative families
- keep the slice open until the full ART sweep returns zero issues
