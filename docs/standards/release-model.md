# Release Model

## Purpose

This document defines how versions are promoted and how runtime drift is treated.

## Release Authority

The platform repo is the release authority.

That means:

- source repos define candidate code
- this repo defines which version is approved for each environment

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
3. update [environments/prod/versions.yaml](../../environments/prod/versions.yaml) in a pull request
4. approve and merge the pull request
5. Argo CD reconciles the cluster runtime
6. Ansible applies host-side changes if required
7. Prometheus and Grafana confirm service health
8. runtime attestation must match the approved manifest

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
