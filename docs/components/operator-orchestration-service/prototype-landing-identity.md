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
persistent session-scoped coordination path. `revoke` invalidates the token and
removes only those exact runtime bindings.

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

This work activates only the identity projection. The OOS and WGCF Prototype
Landing manifests remain fail-closed and `OOS_PROTOTYPE_LANDING_ENABLED` is
forced to `false`. Console wiring and composed conformance must complete before
normal workflow availability is enabled.

## Evidence And Recovery

Receipts bind the source definition, reviewed source heads, App and
installation ids, repository and owner ids, permissions, caller, profile,
session, runtime binding, issue/expiry times, Security review, and rollback.
They never contain credential values.

Suspension stops new projection. Revocation invalidates the issued token,
removes the OOS Secret, environment entries, and mounts, and retains source,
reviews, coordination state, and receipts. Definition rollback restores prior
reviewed Platform source; it does not delete a Prototype or rewrite Studio
`main`.

## Delivery Sequence

1. OOS source workflow #1088 and Security review #1089 are complete.
2. Platform #1090 defines, commissions, projects, rotates, and revokes this identity.
3. Console #1091 binds the browser projection to OOS without gaining source authority.
4. Composed conformance #1092 enables the source-owned runtime gates and proves all positive and negative paths before normal availability.
