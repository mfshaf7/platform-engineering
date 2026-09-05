# Workspace Intake Git Identity

## Role And State

Platform defines one GitHub App identity for the OOS Workspace Intake
workflow. Its only repository is `mfshaf7/workspace-governance`, immutable id
`1212447211`, owned by user id `244414185`. This is a personal-account
repository, not an organization repository. The existing repository
provisioning and lifecycle Apps must not be reused: their administrative
authority and organization-specific commissioning checks are different.

The definition is **selected, not active**. No App or installation id has
been assigned by this work. No credential is issued, mounted or enabled.
The authoritative definition is
[workspace-intake-identity.yaml](../../../security/workspace-intake-identity.yaml).

## Primary Operator Path

```bash
make workspace-intake-identity ACTION=validate
python3 scripts/test_workspace_intake_identity.py
```

Validation is read-only and reports the exact definition digest. It does not
verify a provider installation or permit runtime writes. There is deliberately
no commission or deliver command in this source-definition child (#1065).
The approved activation child #1082 will add the real provider procedure and
its API-compatible receipt after Security #1066 reviews the complete source.

## Least Privilege

The exact permission set is Metadata read, Contents write, Pull requests
write, and Checks read. The latter lets OOS read exact-head owner CI evidence;
it cannot publish checks. There are no events, administration, secrets,
workflow-write, repository-creation or deletion permissions. Tokens select
exactly one immutable repository and expire within one hour. Rotation occurs
before the last 15 minutes; expiry or revocation stops advancement, not review
history or canonical readback evidence.

Permissions alone do **not** prove merge or main-write denial. GitHub's merge
endpoint uses Contents write, which is also needed for review source. Activation
must therefore prove enforced main-update restrictions admitting only the
approved human actors, with no bypass for this App, as well as required review
and trusted owner checks. A code-level absence of a merge endpoint is not a
replacement for that provider control. If the actual repository/account cannot
enforce these restrictions, activation is blocked, not silently broadened.
See [GitHub pull request permissions](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request)
and [ruleset restrictions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).

OOS enforces the `intake/<digest>` branch namespace and the intake-register
file boundary, invokes the committed Workspace Governance owner command, and
verifies reviewed source and merged content. Those are application controls,
not claims that GitHub tokens have per-file permission scopes. Normal
operator work is through the Console/OOS API, not Platform scripts or ambient
`gh` credentials. Workspace Governance remains canonical; OOS coordination is
not another inventory database.

## Custody And Activation Evidence

The private key remains in Platform's dedicated Vault path. OOS receives only
a short-lived installation token through a read-only Secret directory, without
a `subPath` mount that would prevent rotation. The file path is passed through
`OOS_WORKSPACE_INTAKE_TOKEN_FILE`; OOS re-reads the file for requests. No private
key, token, or authorization header belongs in source, ART, receipts or logs.

Activation must bind the definition digest, reviewed source heads, App and
installation identities, exact repository and owner ids, permissions, caller,
profile, session and execution, issue/expiry/recording times, Security receipt,
and revocation/rollback receipt. A new activation cannot reuse stale source or
session evidence. The live gate must verify both successful branch/PR access
and denied merge/main/administration/unrelated-repository access. Filesystem
configuration tests do not substitute for these provider proofs.

Suspension stops new requests. Revocation invalidates the token and removes
only its runtime projection. Both preserve workflow history, reviews, canonical
Git and receipts. Definition rollback restores the prior reviewed source; it
does not undo an already merged entrant or delete any repository.

## Owner Sequence

1. #1065 defines and validates this inactive contract.
2. #1067/#1068 complete the source and Console adapters.
3. #1066 accepts or rejects exact source and the trust boundary.
4. #1082 commissions the selected identity and proves delivery/revocation.
5. #1069 proves the composed intake workflow with real owner receipts.

Inventory and lifecycle source paths are not authorized by this intake-only
definition. Their later contract and workflow work must explicitly extend the
reviewed boundary before access is enabled. Stage and production are excluded.
