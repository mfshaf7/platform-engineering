# Commission Product Lifecycle Maintenance

This is the primary Platform operator procedure for Product Publication and
Workspace Registry lifecycle maintenance in local `dev-integration`. It closes
Delivery ART work item `#1273` through the existing `refinement-catalog`
composition. Do not create another service, identity, database, workflow,
control plane, or ART item.

## Authority Boundary

- Workspace Registry alone retires and restores the product record.
- Product Publication alone unpublishes, archives, restores, and republishes.
- The product owner repository supplies each reviewed manifest.
- OOS owns workflow journals and terminal receipts.
- WGCF owns readiness receipts and its immutable ledger.
- Security owns the accepted target and action boundary.
- Platform activates the composition, enforces the order, and verifies evidence.

Platform never edits either owner directly. The browser receives no owner
credential. `client`, `public`, direct listed restoration, and any skipped owner
boundary remain denied.

## Exact Sequence

Use only this order:

1. Confirm Registry `active` and publication `internal`. Commit a fresh
   active/`internal` owner manifest.
2. Unpublish `internal -> unlisted` through Product Publication.
3. Retire through Workspace Registry and merge the exact human-reviewed owner
   change.
4. Commit a fresh schema-v2 retired/`unlisted` manifest bound to the retirement
   receipt and history event.
5. Archive `unlisted -> archived` through Product Publication.
6. Restore through Workspace Registry and merge the exact human-reviewed owner
   change.
7. Commit a fresh schema-v2 active/`unlisted` manifest bound to the restoration
   receipt, history event, and prior retirement event.
8. Restore publication `archived -> unlisted`.
9. Publish `unlisted -> internal` to restore the original audience baseline.
10. Commit a fresh schema-v2 active/`internal` final manifest and reconcile all
    owners.

Each owner-manifest change is owner-repo maintenance with Agent Gary as author
and the human operator as reviewer and merger. Never copy `manifest_source`
from an earlier command.

## Activate Exact Sources

Reconcile the existing composition with the merged OOS and WGCF heads and the
reviewed Platform checkout:

```bash
python3 scripts/dev_integration.py up \
  --composition refinement-catalog \
  --workspace-root /home/mfshaf7/projects \
  --repo-path operator-orchestration-service=/home/mfshaf7/projects/operator-orchestration-service \
  --repo-path workspace-governance-control-fabric=/home/mfshaf7/projects/workspace-governance-control-fabric \
  --repo-path platform-engineering=<reviewed-platform-checkout>

make governance-console-product-publication ACTION=validate ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=activate ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

The Console checkout must be current clean `main` and descend from the
Security-reviewed minimum. This permits each required reviewed owner-manifest
commit while retaining exact-head evidence in the Platform receipt.

If a required provider credential is absent, stop and deliver the existing
Platform-owned identity. Do not use an ambient PAT or human browser credential.

## Record Durable Sequence Evidence

After the owner workflows complete, write one operator-private file at:

`~/.local/state/platform-engineering/product-publication/sequence-evidence.json`

It contains only stable identifiers and no credential or owner payload:

```json
{
  "schema_version": 1,
  "product_id": "product:governance-operations-console",
  "publication_request_ids": {
    "unpublish": "product-publication-request:...",
    "archive": "product-publication-request:...",
    "restore": "product-publication-request:...",
    "publish": "product-publication-request:..."
  },
  "inventory_request_ids": {
    "retire": "workspace-inventory-lifecycle-request:...",
    "restore": "workspace-inventory-lifecycle-request:..."
  },
  "final_manifest": {
    "revision": "<40-character reviewed owner commit>",
    "digest": "sha256:<canonical manifest digest>",
    "source_revision": "<40-character product source snapshot>"
  }
}
```

The verifier rereads every request from OOS, every lifecycle result from
Workspace Registry, and every manifest from Git. It rejects copied manifests,
missing review boundaries, broken receipt chains, reordered history, stale
Registry evidence, and cross-boundary grants. The commissioning command itself
executes the authorization, ordering, stale-manifest, invalid-target, replay,
and interruption probes and records content-addressed denial evidence; the
operator does not assert those outcomes by hand.

## Commission And Verify

```bash
make governance-console-product-publication ACTION=commission ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=verify-operating ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=verify-process-crash ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

`commission` performs readback of the full sequence, named fail-closed cases,
OOS process loss, restart, bounded rollback, reactivation, and final readback.
It preserves Workspace Inventory history, source reviews, WGCF ledger entries,
OOS journals, publication receipts, and operator evidence.

## Interruption And Recovery

Safe durable interruption states are active/`unlisted`, retired/`unlisted`,
retired/`archived`, and active/`archived`. Reread Workspace Registry and the
latest Product Publication receipt, then continue with the next exact step.
Never direct-edit a product state or manufacture a compensating receipt.

Rollback removes only the Product Publication runtime bindings and Console
metadata:

```bash
make governance-console-product-publication ACTION=rollback ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

Restore with `ACTION=activate`, then require `ACTION=status` and the two
operating verifiers before claiming availability.
