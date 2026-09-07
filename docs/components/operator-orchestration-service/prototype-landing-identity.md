# Prototype Landing Identity

## Role And State

Platform owns one GitHub App identity for OOS Prototype Landing. Its only
repository is `mfshaf7/workspace-prototype-studio`, immutable id `1231020532`,
owned by user id `244414185`. Workspace Intake and repository-provider Apps
must not be reused because they have different repositories, operations, and
review boundaries.

The source definition remains `selected-not-active`; live projection is proven
by value-free receipts instead of mutable Git state. The definition is
[prototype-landing-identity.yaml](../../../security/prototype-landing-identity.yaml).

## Primary Operator Path

```bash
make prototype-landing-identity ACTION=validate
python3 scripts/test_prototype_landing_identity.py
```

`commission` verifies the exact App, installation, account, repository,
permissions, event set, and selected-repository token, then revokes the proof
token. `deliver` repeats those checks and projects one short-lived token into
the active `accepted-idea-delivery` session. It also projects the existing WGCF
service-caller credential, a read-only Prototype Studio authority mount, and a
persistent session-scoped coordination path. Repeating `deliver` replaces the
projection and revokes the prior token. `suspend` blocks new requests while
retaining the identity projection and coordination state. `revoke` invalidates
the token and removes only those exact runtime bindings.

Use `make prototype-landing-identity ACTION=<action> ARGS="..."`; command help
lists the required source revisions, session manifest, caller, provider, WGCF,
and receipt inputs. Private-key and WGCF secret files must be regular files with
mode `0600` or stricter.

## Least Privilege

The App has Metadata read, Contents write, Pull requests write, and Checks
read for exactly `workspace-prototype-studio`. OOS uses that authority only for
`prototype-landing/<binding-digest>` review branches and the Prototype Studio
paths declared by the Landing plan. It cannot merge, write `main`, administer
or delete repositories, mutate referenced source, or use unrelated repository
authority.

GitHub permissions do not provide path-level restrictions, and the merge API is
covered by Contents write. Activation therefore also requires a repository
ruleset that restricts `main` updates to approved humans, denies App bypass,
requires exact-head owner validation and review, dismisses stale approvals, and
denies force push and branch deletion. If the provider cannot enforce this,
commissioning is blocked.

## Runtime And Secret Boundary

The private key stays in Platform Vault at the path in the source definition.
OOS receives only a rotating installation token through a read-only Secret
directory. The volume is not mounted with `subPath`, so token replacement is
visible to the client when it rereads the file. The WGCF caller secret is
projected from the same Platform-controlled Secret as an environment binding;
neither secret is written to source, output, logs, receipts, or ART evidence.

The Studio checkout is read-only in the OOS pod. OOS creates disposable exact-
revision clones for source preparation. Coordination state is stored under the
active local profile session and survives pod restarts; revocation retains that
state and all source/review evidence.

The active source definition enables the OOS runtime gate only after Security
#1111, WGCF #1112, and OOS #1113 have landed. Platform delivery projects those
exact bindings together; a partial or mismatched contract fails closed. Console
wiring and composed conformance remain separate downstream proof in #1115.

## Evidence And Recovery

Receipts bind the source definition, reviewed source heads, App and
installation ids, repository and owner ids, permissions, caller, profile,
session, runtime binding, issue/expiry times, Security review, and rollback.
They never contain credential values.

Suspension sets the OOS gate false and retains the current credential, mounts,
state, reviews, and receipts so delivery can resume without reconstructing
workflow state. Revocation invalidates the issued token, removes the OOS Secret,
environment entries, and mounts, and retains source, reviews, coordination
state, and receipts. Definition rollback restores prior reviewed Platform
source; it does not delete a Prototype or rewrite Studio `main`.

## Delivery Sequence

1. Security #1111 approves the bounded activation contract.
2. WGCF #1112 and OOS #1113 land their source-owned gates and runtime bindings.
3. Platform #1114 commissions the exact composition, enables the OOS gate, and proves restart, rotation, suspension, revocation, and recovery.
4. Console and composed conformance #1115 prove operator-path availability without granting browser-side source authority.
