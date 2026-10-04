# Workspace Intake And Inventory Git Identity

## Role And State

Platform defines one GitHub App identity for the OOS Workspace Intake and
Active Inventory workflows. Its only repository is `mfshaf7/workspace-governance`, immutable id
`1212447211`, owned by user id `244414185`. This is a personal-account
repository, not an organization repository. The existing repository
provisioning and lifecycle Apps must not be reused: their administrative
authority and organization-specific commissioning checks are different.

The Git-tracked definition remains a stable **selected, not active** source
contract; live activation state is recorded in value-free Platform receipts,
not written back into the contract. The authoritative definition is
[workspace-intake-identity.yaml](../../../security/workspace-intake-identity.yaml).

## Primary Operator Path

```bash
make workspace-intake-identity ACTION=validate
python3 scripts/test_workspace_intake_identity.py
```

`validate` is read-only. `commission` verifies the exact App, installation,
account, repository id, permissions, event set, and one-repository token scope,
then revokes its proof token. `deliver` repeats those checks before projecting
one short-lived installation token into the admitted OOS dev-integration
runtime. `status` executes authenticated, non-mutating Intake preparation and
Inventory registry requests inside the OOS pod, verifies that both bind the
same canonical authority revision, and proves an invalid caller is denied.
`revoke` invalidates the token and removes its projection. Use
`make workspace-intake-identity ACTION=<action> ARGS="..."`; the command help
lists the required source-revision, caller, provider, session, and receipt
arguments.

For the approved Workspace operations composition, repeat the source argument
for this exact set; the Platform revision must be the clean executing checkout:

```text
--source-revision workspace-governance=9718ce9eea04049541a1fb44f0b7cdc0ac823687
--source-revision workspace-governance-control-fabric=3d04ccaa8a751dfcb743c06b253299ee028c8f46
--source-revision operator-orchestration-service=968643ad3dca86366ae417ebe77a23ba7c2c2cb6
--source-revision governance-operations-console=9347794a138f3649bb6ef5b7db057524d1c1e26d
--source-revision security-architecture=3cb26a024fce1d01ff8eb80899d8f50299982c9a
--source-revision platform-engineering=<current-clean-HEAD>
```

The Inventory extension is approved only for the exact repaired OOS, Workspace
Governance, WGCF, Console, and Security revisions pinned in
`security/workspace-intake-identity.yaml`. For a `refinement-catalog` session,
`deliver` and `status` also require the executing Platform `HEAD` and the exact
accepted owner revisions in their source-revision arguments. A different or
partial set fails closed. The approved source contract is still not operating
evidence; only a successful direct runtime proof produces that evidence.

The activation source is ART #1082 and the exact-source Security decision is
#1066. A runtime receipt never changes the source definition into a mutable
state database.

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

OOS enforces the `intake/<digest>`, `inventory/<digest>`, and
`inventory-lifecycle/<digest>` branch namespaces and restricts source writes
to the intake register, the selected active-inventory contract, and the
inventory history. It invokes the committed Workspace Governance owner
commands and verifies reviewed source and merged content. Those are application controls,
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

Every activation receipt binds the definition digest, reviewed source heads, App and
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

The Inventory and lifecycle source paths are accepted for the exact local
composition and remain subject to direct runtime proof. Stage and production
are excluded.
