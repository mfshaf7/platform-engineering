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
Seven-repository installation readback, fresh-key commissioning, and
one-repository token proof are **pending**; this record is not an activation
receipt.

The focused Agent source identity tests (13 cases), contract validator,
repository-structure validator, and governance-doc validator passed locally.
The broader `make validate` was attempted but could not complete its unrelated
Temporal controlled-proof tests because the local WSL environment has no
`docker` executable; the PR's CI validation remains required.

## Follow-Up Actions

- Commission a replacement private key from a local `0600` PEM through the
  Platform Vault boundary, verify the exact seven-repository installation and
  one-repository tokens, then revoke the exposed prior GitHub App key.
- Land and validate this Platform source change, then let OOS `#1147` pin its
  merged revision and admit the two additional owner repositories.
