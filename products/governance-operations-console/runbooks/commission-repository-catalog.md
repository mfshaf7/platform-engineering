# Commission Repository And Catalog Operation

This is the primary Platform operator surface for the reviewed Repository to
Delivery Catalog path in local `dev-integration`. It extends the existing
`accepted-idea-delivery`, Console session-projection, and cross-domain
activation controls. It does not create a second workflow or control plane.

The command proves this capability specifically. Generic Console activity or
process health is not Repository/Catalog evidence.

## Scope

The policy pins the exact OOS, Console, WGCF, Workspace Governance, Security,
and architecture inputs accepted for ART `#1231`. The Console browser receives
no owner credential. The Console server calls OOS, OOS reads Workspace
Inventory and calls WGCF, and OOS alone performs the reviewed Catalog mutation
and canonical readback.

This path is loopback-only and single-operator. It does not prove stage,
production, remote, shared, or multi-user readiness.

## Prepare The Existing Composition

Reconcile the registered composition from the exact reviewed source checkouts:

```bash
make devint-up COMPOSITION=refinement-catalog EXTRA_ARGS="\
  --repo-path operator-orchestration-service=<exact-oos-checkout> \
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

Deliver the existing Workspace Intake identity if composition status reports
`credential-required`. Do not replace a failed identity or authority check with
fixture data.

## Validate And Activate

If an approved repository is selected through a clean exact-revision worktree,
pass the same `--repo-path repo=/absolute/path` override to every action.

```bash
make governance-console-repository-catalog ACTION=validate
make governance-console-repository-catalog ACTION=activate
make governance-console-repository-catalog ACTION=status
```

Activation upgrades the existing managed Console services. It issues the
Platform session projection, keeps OOS and WGCF credentials in the private
server environment, selects the reviewed repository-readiness contract bundle
from the exact WGCF image, and requires live Workspace Registry, Catalog, OOS,
and WGCF projections before writing a receipt.

## Capability-Specific Rehearsal

The governed evidence profile runs the full sequence with one command:

```bash
make governance-console-repository-catalog ACTION=commission
```

`commission` validates and activates the reviewed sources, proves status,
performs the Catalog rehearsal, proves restart, exercises rollback and cleanup,
and finishes with a fresh activation and status. Its aggregate receipt binds
the content digests of every child receipt and confirms final availability.
The individual commands below remain available for bounded diagnosis and
operator recovery.

```bash
make governance-console-repository-catalog ACTION=catalog-rehearse
make governance-console-repository-catalog ACTION=restart
make governance-console-repository-catalog ACTION=status
```

`catalog-rehearse` performs one genuine first-use link for an active Workspace
Inventory repository that is not already an Owner Repo Catalog value. It then
reuses the returned readiness reference for an existing-value edit and proves
canonical readback. The resulting active Catalog value is valid workspace
truth, not disposable test data.

The same action proves that false or stale readiness, an unavailable session,
OOS loss, WGCF loss, and Catalog-backend loss all fail closed without changing
the accepted Catalog value. It restores each deliberately disconnected owner
before continuing. `restart` replaces the OOS pod, restarts the managed
loopback services, and requires the capability to become current again.

Receipts are retained under
`~/.local/state/platform-engineering/governance-console-cross-domain/receipts/`.
They contain source, receipt, denial, restart, and boundary metadata but no
credentials or raw owner payloads.

## Rollback And Cleanup

```bash
make governance-console-repository-catalog ACTION=rollback
make governance-console-repository-catalog ACTION=cleanup
make governance-console-repository-catalog ACTION=activate
make governance-console-repository-catalog ACTION=status
```

Rollback stops only the managed Console/tunnel services, removes the dedicated
WGCF reader binding, and revokes the Console session projection. Cleanup also
removes generated units and private credential/projection files. Both preserve
Workspace Inventory, Catalog values and history, ART, WGCF evidence, owner
profile data, Git history, Security decisions, and durable receipts.

Final routine availability requires a fresh `activate` and `status` after the
rollback/cleanup proof. Never cite a generic activity receipt in place of the
Repository/Catalog receipt.
