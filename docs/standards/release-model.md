# Release Model

## Purpose

This document defines how versions are promoted and how runtime drift is treated.

For the shared release-governance tiers and the required candidate,
verification, readiness, and prod-verification objects, see
[governed-release-control-model.md](governed-release-control-model.md).

## Release Authority

The platform repo is the release authority.

That means:

- source repos define candidate code
- this repo defines which version is approved for each environment
- stage or prod readiness still depends on the matching release-governance
  objects for the workload tier, not on version pins alone

## Version Objects

Each environment pins:

- runtime image repository, tag, and digest
- source commit SHAs for participating product repos
- platform repo commit SHA
- chart versions
- observability chart versions

These pins live under:

- [environments/prod/versions.yaml](../../environments/prod/versions.yaml)

## Runtime Attestation Requirement

Production must be able to report:

- deployed image digest
- participating source SHAs
- deployed platform manifest version
- Argo CD application revision

If runtime cannot report those values, production is not fully attestable.

## Drift States

| State | Meaning | Operational response |
| --- | --- | --- |
| `green` | runtime matches approved manifest | normal operation |
| `yellow` | runtime healthy but version or config mismatch exists | reconcile in a planned maintenance step |
| `red` | runtime version unknown, unauthorized live patching, or unreconciled drift | treat as deployment incident |

## Promotion Path

1. build candidate artifacts
2. publish metadata and attestations
3. derive source pins from the actual local repo checkouts instead of copying
   SHAs by hand where possible
4. compute the deterministic source-bundle tag from those pins, clear any stale
   digest from the previous artifact candidate, and reject build output that no
   longer matches the current tag
5. update [environments/prod/versions.yaml](../../environments/prod/versions.yaml) in a pull request
6. approve and merge the pull request
7. Argo CD reconciles the cluster runtime
8. Ansible applies host-side changes if required
9. Prometheus and Grafana confirm service health
10. runtime attestation must match the approved manifest

Promotion is not complete from version reconciliation alone. The governed
release-control model still requires the matching stage readiness or
post-promotion verification state for the workload tier.

## Rollback Path

Rollback means:

- revert or replace the pinned version in the platform repo
- allow Argo CD to reconcile back to that version
- rerun host-side Ansible if the rollback includes host-side changes
- verify that runtime now matches the previous approved state

Rollback does not mean:

- manual live container editing
- ad hoc workspace copy replacement
- changing code in the running environment without recording it in Git
