# Commission Product Publication

This is the primary Platform operator surface for Product Publication in local
`dev-integration`. It reuses the composition commissioned by Delivery ART work
item `#1258` and recommissions its audience boundary for work item `#1264`. It
does not create another service, identity, database, workflow, or ART item.

## Boundary

The path is single-operator and loopback-only. The Console submits intent with
its existing private OOS caller and verified Platform session. OOS owns the
journal and terminal owner receipt. WGCF owns readiness and its immutable
ledger. Workspace Governance owns publication policy and product identity. The
product repository owns the manifest. Security owns acceptance. Platform owns
composition, runtime proof, rollback, and teardown.

Only `governance-operations-console` may move from owner-manifest evidence at
`unlisted` to the `internal` target under this commissioning decision.
`unlisted`, `client`, `public`, and `archived` remain denied as targets. The
owner-manifest binding is publication evidence, not an endpoint, access route,
or access grant. Remote, shared, multi-user, stage, production, AI-driven, or
real-client-data operation is not approved.

## Reconcile Exact Sources

Use the merged OOS and WGCF activation revisions and the reviewed Console
source. The policy separately binds each Security-reviewed capability revision
and proves that the selected exact runtime revision descends from it. The same
rule applies to Workspace Governance authority and the owner manifest, whose
reviewed bytes must remain unchanged at the current merged runtime heads. An
inactive or superseded reviewed commit is never represented as the running
source. A Platform worktree may be selected explicitly while it is under review.

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

`commission` reads and verifies the exact existing #1258 internal publication;
it does not issue a duplicate version-zero publication or rewrite its durable
history. It then proves unauthorized caller denial, exact Security mismatch denial, stale
manifest denial, conflicting replay denial, denial of all four inactive target
postures, and zero cross-boundary grants. It deliberately removes the OOS
process, proves an attempted operation cannot claim success or create state,
restores OOS, restarts OOS, WGCF, and the Console, proves the same receipt,
removes the Product Publication runtime bindings, proves disconnected mode,
restores the reviewed bindings, and proves final readback.

The command keeps the OOS state directory and WGCF ledger. Rollback and cleanup
never delete publication history, readiness evidence, source, Security
decisions, or operator receipts.

## Operating Verification And Rollback

```bash
make governance-console-product-publication ACTION=verify-operating ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=verify-process-crash ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-product-publication ACTION=rollback ARGS="\
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

Operating and process-crash verification accept only a digest-valid
commissioning receipt for the exact current Platform revision and re-read the
durable publication. The process-crash verifier additionally requires the
interrupted request to be absent and one OOS replica to have been restored.
Rollback removes the Console metadata and OOS/WGCF runtime bindings while
preserving the journal, ledger, and value-free Platform receipts. Restore with
`ACTION=activate`; confirm with `ACTION=status`.
