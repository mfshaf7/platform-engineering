# Operate the complete Console runtime

This is the primary Platform operator surface for the complete local
Governance Operations Console runtime. It composes the existing
`refinement-catalog`; it does not create another runtime, workflow engine, or
authority plane.

The Console submits operator intent to OOS. OOS authenticates, persists, and
coordinates the bounded command. The Platform provider exposes only the
finite actions declared in `complete-runtime-policy.yaml` and performs effects
through the existing `dev_integration.py` owner command. Console and browser
processes never receive the Platform provider credential.

## Security gate

Source validation is expected to report `security-pending` before work item
`#1303` lands. Activation remains blocked in that state.

Security owns these two files in `security-architecture`:

- `docs/reviews/components/2026-10-15-governance-console-platform-operation.md`
- `docs/reviews/components/2026-10-15-governance-console-platform-operation.yaml`

The YAML decision must accept gate `gate:platform-operation-security`, work
item `#1303`, the current Architecture Packet reference, the exact reviewed
revisions for Console, OOS, Platform, Workspace Governance, and WGCF, and the
exact reviewed Platform tree. The Markdown review must contain those same
bindings. Runtime reads the decision from current clean Security `origin/main`
and materializes private policies; no post-review Platform source-pin edit is
required.

After merge, persistent services use the workspace main checkout when its
clean committed tree matches the reviewed worktree and `origin/main`. This
keeps the provider and composition auto-resume unit available after the
review worktree is retired. A different or dirty tree is never substituted.
Before removing the review worktree, activate from the current main checkout
and verify both services' `WorkingDirectory` and `ExecStart` paths:

```bash
systemctl --user show governance-console-platform-operation-provider.service \
  workspace-devint-accepted-idea-delivery-mfshaf7.service \
  -p WorkingDirectory -p ExecStart
```

Every referenced source directory must survive cleanup. Successful branch
cleanup alone does not prove runtime restart readiness.

That private activation policy enables WGCF's read-only workspace-continuity
projection only for the exact reviewed composition. It reuses the existing
server-side Console WGCF caller credential and removes the enablement during
rollback; neither the browser nor Console receives a new credential.

The same accepted composition activates repository provisioning through the
existing `gate:repository-custody-runtime-activation` boundary. Platform reads
the dedicated GitHub App private key from its existing Vault path, uses the
existing repository-provisioning identity tool to mint and project one
short-lived organization installation token, activates WGCF custody readiness,
mounts operator-private OOS custody state, and writes only the policy and
credential-binding references into the Console server environment. The token
and private key are never written to source, receipts, browser state, or
process arguments. The operator running activation needs a current private
Vault token in `VAULT_TOKEN` or mode-`0600` `~/.vault-token`.

The existing user-systemd lifecycle maintains provisioning and the five
previously commissioned Proposal Target, Prototype Landing, Prototype Maturity,
Prototype Closure and Workspace Intake identities. The existing
`governance-console-repository-credentials` unit names remain compatibility
names for this one timer; no new renewal service is introduced. Only the closed
App/installation set and the existing dedicated identity contracts/Vault paths
are allowed. Missing or disabled owner bindings require their existing
commissioning procedure; renewal cannot activate a workflow or widen scope.

The timer checks every five minutes and renews when fewer than twenty minutes
remain. It reuses exact-App provider validation, checks current Security/source
bindings, and verifies the existing Secret ownership and credential binding.
All required Vault keys are checked before replacement. Resource-version
compare-and-swap uses the original identity producer's server-side Apply field
manager, preserving its recovery command and unrelated Secret fields, including
WGCF caller credentials. Native ownership proof is available without provider
issuance or real Secret changes:

```bash
CONSOLE_NATIVE_KUBE_PROOF_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  python3 products/governance-operations-console/scripts/test_console_complete_runtime.py
```

The existing local-cluster/session guard must pass; only uniquely named synthetic
ConfigMaps and synthetic Secrets are created and removed. This reproduces the old
replacement conflict, then proves each actual adapter's recovery compatibility,
stale-version denial and the existing producers' real Secret manifest format.
Temporary private keys are removed on every exit; tokens never
enter process arguments, logs, source, browser state or receipts.

The token batch takes one OOS delivery-version update and bounded rollout.
Unchanged versions do not restart OOS. After a crash between replacement and
consumption, renewal first consumes the retained version instead of minting
another. Readiness proves exact configuration, hash equality with each actual
mounted token, live provider acceptance and exact-one-repository scope. Prior
tokens are revoked after replacement consumption is proven. A process loss
before revocation can leave an old unchanged-scope token valid only until its
original maximum-one-hour expiry. Successful renewal requires normal revocation.
Missing Vault access, stale acceptance, failed consumption or provider denial
remains a visible failure, never readiness or ambient-credential fallback.

The timer requires the active-runtime marker and uses the lifecycle lock
without waiting. Activation, restart, proof, and rollback therefore cannot race
renewal. Rollback stops renewal before revoking the token. Source-only review
does not prove renewal; commissioning forces the complete identity group through
the same refresh path and checks
the active timer and restored readiness. The owner recovery command remains
`ACTION=restart`; routine renewal requires no Console operator or CLI action.

## Commands

Validate source without changing runtime:

```bash
make governance-console-complete-runtime ACTION=validate
```

After the exact Security decision and all reviewed owner revisions are on
clean `main`, activate and inspect:

```bash
make governance-console-complete-runtime ACTION=activate
make governance-console-complete-runtime ACTION=status
```

Recover the admitted services and re-prove current readback:

```bash
make governance-console-complete-runtime ACTION=restart
```

Run the bounded operating proof only during work item `#1291` commissioning:

```bash
make governance-console-complete-runtime ACTION=verify-operating
```

That proof checks authenticated startup, invalid-credential denial, revoked
gate denial, stale-marker denial, provider process-loss recovery, full restart,
rollback, teardown, repository-credential revocation, fresh credential
delivery and renewal, and restoration of executable Console repository provisioning. It
retains only credential-free receipts. The proof holds one operator-private
filesystem lock across the complete lifecycle. A replacement executor waits
on that lock and may reuse the result only when the retained receipt has a
valid content digest, the exact current Security decision and reviewed
revisions, the complete proof shape, and restored normal availability. Stale,
malformed, partial, or different-revision receipts are ignored and cannot
satisfy commissioning.

## Stop and cleanup

`rollback` revokes the short-lived repository-provisioning token, removes its
runtime Secret, removes Console-facing services and OOS/WGCF runtime bindings,
and preserves the existing composition and canonical owner state. `cleanup`
additionally removes generated credentials and private materialized policy.
`teardown` performs cleanup and suspends the complete composition.

```bash
make governance-console-complete-runtime ACTION=rollback
make governance-console-complete-runtime ACTION=cleanup
make governance-console-complete-runtime ACTION=teardown
```

Rollback and teardown never delete ART, Git, OOS workflow, WGCF, Security, or
owner evidence.

The five other bindings predate the Console complete-runtime owner. Rollback
does not delete, disable or revoke them: their last dedicated tokens retain
their original bounded expiry while managed renewal stops. Teardown suspends
the existing composition. Later accepted activation renews stale tokens and
proves consumption; preservation does not promise indefinite availability.

## Failure interpretation

- `Security decision ... unavailable`: `#1303` has not landed at the declared
  path, or Security `main` is not current and clean.
- `missing, stale, revoked, or outside scope`: the decision does not accept
  this exact gate, initiative, work item, or Architecture Packet.
- `not the exact Security-reviewed source`: one owner checkout differs from
  the accepted revision, or the Platform tree differs from the reviewed tree.
- `active runtime does not match`: run `restart` or `activate`; do not edit the
  private policy.
- provider or Console readback unavailable: inspect the named systemd service
  and owner workload, repair the dependency, then run `restart`.
- `repository provisioning ... stale or mismatched`: refresh the Vault-backed
  activation with `ACTION=restart`; do not substitute an ambient `gh` token or
  browser credential.
- `Console repository provisioning is not executable`: inspect the reported
  WGCF, OOS, credential, state, and Console binding instead of bypassing the
  Repository Control surface.

Private state and receipts live below
`~/.local/state/platform-engineering/governance-console-complete-runtime/`.
Do not paste its private files into chat, ART, logs, or source control.
