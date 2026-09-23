# Agent Source Active Owner Scope

## Summary

ART `#1168` replaces Agent Gary's closure-era seven-repository snapshot with
the exact eleven active governed owner repositories. The GitHub App remains a
selected-repository installation and every token remains scoped to one
repository and one Landing Unit.

## Classification

Shared Platform source-identity contract correction in `dev-integration`. No
stage or production deployment and no permission expansion beyond additional
active owner repositories.

## Ownership

Workspace Governance owns active repository inventory. Platform owns the App
definition, exact provider ids, credential custody, token issuance, and
provider readback. OOS `#1169` owns configured-path consumption. Security
`#1166` retains the final lifecycle-context activation decision.

## Root Cause

The Platform and OOS identity contracts retained the seven repositories needed
for Prototype Closure. Context Governance Gateway and the three active
OpenClaw owner repositories were absent even though Agent Gary is the sole
source implementor for active governed work.

## Source Changes

The identity definition and schema now cover the eleven active owners and pin
the authoritative Workspace Governance inventory revision and digest. Focused
tests continue to prove one-repository token isolation and exact provider ids.
The atomic receipt writer also preserves permissions on existing parent
directories while retaining `0600` receipt files.

## Artifact And Deployment Evidence

This is a source and provider-configuration change. It builds no runtime image.
The finalized Review Packet will bind the merged Platform source and provider
commissioning receipt.

## Live Verification

The selected-repository App installation was updated and commissioned through
the Platform operator surface. GitHub returned the exact eleven repository ids,
every proof token was limited to one repository and revoked, and the receipt
confirmed unchanged permissions with `secret_values_embedded: false`.

- receipt digest:
  `sha256:6e6979c8a650b97210e08212d699e41814c561f26842c2cc53f2d58db7cff604`
- receipt location during delivery:
  `/tmp/delivery-1168-agent-source-commission.json`
- outcome: `commissioned-inactive`

Normal OOS lifecycle activation remains gated by `#1169` and the final
Security decision in `#1166`.

## Validation

- `python3 scripts/agent_source_identity.py validate --workspace-repo-inventory /home/mfshaf7/projects/workspace-governance/contracts/repos.yaml`
- `python3 scripts/test_agent_source_identity.py`
- `python3 scripts/validate_repo_structure.py`
- `WORKSPACE_ROOT=/home/mfshaf7/projects OOS_REPO_ROOT=/home/mfshaf7/projects/operator-orchestration-service make validate`
- `git diff --check`

## Follow-Up Actions

- Land OOS preflight consumption under `#1169`.
- Recover `#1164` only after both prerequisites close.
