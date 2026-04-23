# 2026-04-23 Single-Host Scaling Default

## Summary

The shared platform now enforces a single-host scaling default for new product
and component runtime declarations.

On this machine, extra replicas usually add memory cost and operational drift
without giving real host-level resilience. The platform should therefore fail
closed when new runtime surfaces land above replica count `1` without an
explicit recorded exception.

## Classification

- owner repo: `platform-engineering`
- workflow area:
  - shared platform policy
  - runtime sizing
  - validation guardrails

## Ownership

- machine-readable scaling policy:
  `environments/shared/single-host-scaling-policy.yaml`
- enforced validator:
  `scripts/validate_single_host_scaling.py`
- operator standard:
  `docs/standards/single-host-scaling.md`

## Root Cause

The platform already ran several important workloads as singletons, but that
behavior was convention rather than enforced policy.

That left a gap where future products or shared components could quietly land
with multi-replica runtime declarations even though the current platform is a
single-host workstation and the extra replicas would not provide meaningful
availability.

## Source Changes

- added the machine-readable single-host scaling policy contract in
  `environments/shared/single-host-scaling-policy.yaml`
- added `scripts/validate_single_host_scaling.py`
- wired the scaling validator into `make validate`
- added the shared operator standard in
  `docs/standards/single-host-scaling.md`
- updated the product runtime-contract template to require runtime profile and
  exemption disclosure
- aligned the OpenClaw runtime contract with the singleton default

## Artifact And Deployment Evidence

- no live deployment artifact was produced in this guardrail tranche
- this change governs future Git-managed runtime declarations before they land

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `python3 scripts/validate_single_host_scaling.py --repo-root .`
- `git diff --check`

## Follow-Up Actions

- keep any future multi-replica exception explicit in
  `environments/shared/single-host-scaling-policy.yaml`
- extend the same default to new shared charts or product integrations before
  they are promoted into governed stage or prod surfaces
