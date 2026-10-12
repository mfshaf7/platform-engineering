# Commission Product Publication

This is the primary Platform operator surface for Product Publication in local
`dev-integration`. It closes Delivery ART work item `#1258` through the
existing Landing Unit. It does not create another service, identity, database,
workflow, or ART item.

## Boundary

The path is single-operator and loopback-only. The Console submits intent with
its existing private OOS caller and verified Platform session. OOS owns the
journal and terminal owner receipt. WGCF owns readiness and its immutable
ledger. Workspace Governance owns publication policy and product identity. The
product repository owns the manifest. Security owns acceptance. Platform owns
composition, runtime proof, rollback, and teardown.

Only `governance-operations-console` may move from `unlisted` to `internal`
under this commissioning decision. Client, public, archived, remote, shared,
multi-user, stage, production, AI-driven, or real-client-data operation is not
approved.

## Reconcile Exact Sources

Use the merged OOS and WGCF activation revisions and the reviewed Console
source. A Platform worktree may be selected explicitly while it is under
review.

```bash
python3 scripts/dev_integration.py up \
  --composition refinement-catalog \
  --workspace-root /home/mfshaf7/projects \
  --repo-path operator-orchestration-service=/home/mfshaf7/projects/operator-orchestration-service \
  --repo-path workspace-governance-control-fabric=/home/mfshaf7/projects/workspace-governance-control-fabric \
  --repo-path platform-engineering=<reviewed-platform-checkout>
```

## Validate And Commission

```bash
make governance-console-product-publication ACTION=validate ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=commission ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

`commission` performs one exact internal publication and durable readback. It
then proves unauthorized caller denial, exact Security mismatch denial, stale
manifest denial, conflicting replay denial, broader-posture denial, and zero
cross-boundary grants. It restarts OOS, WGCF, and the Console, proves the same
receipt, removes the Product Publication runtime bindings, proves disconnected
mode, restores the reviewed bindings, and proves final readback.

The command keeps the OOS state directory and WGCF ledger. Rollback and cleanup
never delete publication history, readiness evidence, source, Security
decisions, or operator receipts.

## Operating Verification And Rollback

```bash
make governance-console-product-publication ACTION=verify-operating ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=rollback ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

Operating verification accepts only a digest-valid commissioning receipt for
the exact current Platform revision and re-reads the durable publication.
Rollback removes the Console metadata and OOS/WGCF runtime bindings while
preserving the journal, ledger, and value-free Platform receipts. Restore with
`ACTION=activate`; confirm with `ACTION=status`.
