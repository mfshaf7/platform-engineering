# Agent Source Closure Repository Scope

## Summary

ART `#1146` extends the exact Agent Gary source installation definition from
five to seven selected repositories. It follows the merged Security delta in
ART `#1145`; it does not grant merge, default-branch, or repository-admin power
to the App.

## Classification

Shared Platform source-identity contract and GitHub provider enforcement in
the `dev-integration` source path. No stage or production deployment.

## Ownership

Platform owns the App definition, credential custody, token issuance, and
provider checks. Security owns the [scope decision](https://github.com/mfshaf7/security-architecture/blob/7523dd5cce3bbac5fd35e4d21c8b7ad8d65b757a/docs/reviews/components/2026-09-13-agent-gary-closure-source-scope.md).
OOS `#1147` owns consumer adoption. The human repository owner administers
GitHub rulesets and reviews Agent-authored source.

## Root Cause

The Platform and OOS allowlists still covered five repositories after Closure
work needed Control Fabric and Console. Provider readback also found no
`main` ruleset on Platform, Security, OOS, Control Fabric, or Console.

## Source Changes

This Landing Unit updates the exact seven-repository definition, its schema,
focused tests, and [operator guidance](../../components/operator-orchestration-service/agent-source-identity.md).
The Security decision is pinned to the merged revision above.

## Artifact And Deployment Evidence

No image or runtime deployment is involved. On 2026-09-13, the human GitHub
administrator created active `main` rulesets with no bypass actor:

| Repository | Ruleset id | Required GitHub Actions checks |
| --- | ---: | --- |
| `platform-engineering` | 23138464 | `validate` |
| `security-architecture` | 23138484 | `validate-security-evidence` |
| `operator-orchestration-service` | 23138486 | `validate-governance-docs` |
| `workspace-governance-control-fabric` | 23138488 | `governance-bootstrap`, `runtime-images` |
| `governance-operations-console` | 23138493 | `repository` |

Every required check was observed on the repository's current `main` with
GitHub Actions integration id `15368`. Each ruleset requires one current-head
approval, dismisses stale approvals, requires a different last-push approver
and resolved conversations, and denies deletion and non-fast-forward updates.

## Live Verification

`gh api repos/mfshaf7/<repository>/rules/branches/main` returned the four
effective rule types (`deletion`, `non_fast_forward`, `pull_request`, and
`required_status_checks`) for each of the five repositories above.
The replacement key was imported from a temporary `0600` WSL copy into the
Platform Vault path. Platform `commission` authenticated the expected App and
installation, issued and revoked one separately scoped proof token for each
of the seven approved repositories, and observed their exact provider ids.
The receipt is secret-free (`secret_values_embedded: false`), records
`commissioned-inactive` at `2026-09-13T06:01:01Z`, and has SHA-256 digest
`3effdfd043ecb385528a046d5a25b4aff0e6698d6355fc4c87d669a9e72071e4`.
The temporary WSL key copy was retired by the importer. The operator confirms
that the exposed prior key was deleted in GitHub. That deletion was not
independently read back through the Platform commission command.

The seven approved repositories are individually proven accessible. An
independent readback that the installation has **no additional selected
repositories** remains pending; this record is not an activation receipt.

The focused Agent source identity tests (13 cases), contract validator,
repository-structure validator, and governance-doc validator passed locally.
The broader `make validate` was attempted but could not complete its unrelated
Temporal controlled-proof tests because the local WSL environment has no
`docker` executable; the PR's CI validation remains required.

## Follow-Up Actions

- Prove that the provider installation contains no repositories outside the
  approved seven without issuing a broad runtime source token.
- Land and validate this Platform source change, then let OOS `#1147` pin its
  merged revision and admit the two additional owner repositories.
