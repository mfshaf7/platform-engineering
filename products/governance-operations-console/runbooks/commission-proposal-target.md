# Commission Proposal Target

This is the primary Platform operator surface for Proposal-to-Prototype target
application in local `dev-integration`. It closes Delivery ART work item
`#1236` through the existing landing unit. Do not create another ART child for
identity creation, runtime activation, proof, rollback, or recovery.

## Boundaries

- The browser calls only same-origin Console routes.
- Console holds only its OOS caller credential.
- OOS alone receives the dedicated Proposal Target installation token and
  coordinates source preparation, review observation, and Proposal
  acknowledgement.
- Prototype Studio owns the two public-safe capture files and target receipt.
- The GitHub App may open a review but cannot approve or merge it. A human must
  approve and merge the exact checked head.
- A prepared branch or merged pull request is not success. Only Studio
  readback plus canonical Proposal acknowledgement is success.

## Bring Up The Exact Sources

Reconcile the registered composition from the exact reviewed OOS and Platform
checkouts, then deliver the dedicated identity by following
[Proposal Target Identity](../../../docs/components/operator-orchestration-service/proposal-target-identity.md).

```bash
make devint-up COMPOSITION=refinement-catalog EXTRA_ARGS="\
  --repo-path operator-orchestration-service=<exact-oos-checkout> \
  --repo-path platform-engineering=<reviewed-platform-checkout>"

make governance-console-proposal-target ACTION=validate ARGS="\
  --repo-path operator-orchestration-service=<exact-oos-checkout> \
  --repo-path platform-engineering=<reviewed-platform-checkout>"
make governance-console-proposal-target ACTION=activate ARGS="\
  --repo-path operator-orchestration-service=<exact-oos-checkout> \
  --repo-path platform-engineering=<reviewed-platform-checkout>"
make governance-console-proposal-target ACTION=status ARGS="\
  --repo-path operator-orchestration-service=<exact-oos-checkout> \
  --repo-path platform-engineering=<reviewed-platform-checkout>"
```

The policy rejects dirty or wrong-head owner checkouts, wrong session source,
missing Security review or architecture binding, and a Prototype Studio head
other than the accepted public-safe revision.

## Positive Operating Proof

Choose one current accepted Proposal whose selected route is `prototype`, whose
repository gate is resolved, and whose prepared handoff remains unapplied.
Read its current same-origin Console projection and retain the exact
`recordRef`, `recordVersion`, `handoffPacketRef`, and status.

Start through the Console only:

```bash
curl --fail-with-body -sS \
  -H 'Content-Type: application/json' \
  -X POST \
  -d @<private-start-command.json> \
  http://127.0.0.1:3317/api/proposals/<proposal-id>/target-application
```

The request file contains `action: start`, the Proposal id, and the exact
source binding. It must not contain GitHub credentials, caller secrets,
operator identity, free-form target content, or a caller-selected Prototype
identity. The first successful response must be `review-required` and name the
exact `workspace-prototype-studio` pull request, Proposal Target branch, base,
and head.

Approve and merge only that exact checked head as the human reviewer. Then send
`action: continue` to the same Console route. Require `applied`, the exact
target receipt, Studio canonical readback, Proposal acknowledgement, and no
Prototype Landing, Maturity, runtime, or implementation claim.

## Negative Proof

Prove each denial without changing canonical source or Proposal completion:

- an invalid Console/OOS caller returns `401`;
- a stale Proposal `recordVersion` is rejected;
- a changed Prototype Studio `main` revision requires fresh preparation;
- a caller-selected Prototype identity or extra public field is rejected;
- an unreviewed or wrong-head pull request cannot complete;
- a replay with conflicting bindings is rejected; and
- OOS or provider loss cannot produce an applied receipt.

Record only status codes, bounded error codes, source revisions, review ids,
receipt references, and digests. Do not retain request bodies, credentials, or
public-source-unsafe Proposal content.

Store the seven outcomes in one operator-private JSON file with
`schema_version: 1` and an `outcomes` object keyed by
`invalid-caller`, `stale-record-version`, `changed-studio-main`,
`caller-selected-prototype`, `unreviewed-wrong-head`, `conflicting-replay`,
and `provider-loss`. Each value contains only `http_status`, `code`, and
`canonical_state_changed: false`. The commissioning command rejects extra,
missing, successful, or non-private evidence.

## Restart, Rollback, And Final Availability

```bash
make governance-console-proposal-target ACTION=restart
make governance-console-proposal-target ACTION=status
make governance-console-proposal-target ACTION=rollback
make proposal-target-identity ACTION=revoke ARGS="<exact revoke arguments>"
make governance-console-proposal-target ACTION=cleanup
```

Confirm the Proposal Target Secret, environment, and mounts are absent while
the merged Studio capture, canonical Proposal acknowledgement, Git history,
review, and OOS state evidence remain. Finish by reconciling the composition,
redelivering a fresh token, activating the Console loopback services, and
re-running status. Final availability means a current exact-source OOS pod,
read-only dedicated token and Studio mounts, retained state, active loopback
Console services, and no stale credential projection.

Issue the commissioning receipt from the exact completed OOS application and
the ordered receipts produced above:

```bash
make governance-console-proposal-target ACTION=proposal-target-commission ARGS="\
  --application-id <proposal-target-application-id> \
  --negative-proof <operator-private-negative-proof.json> \
  --child-receipt <activate-receipt.json> \
  --child-receipt <initial-status-receipt.json> \
  --child-receipt <restart-receipt.json> \
  --child-receipt <recovered-status-receipt.json> \
  --child-receipt <rollback-receipt.json> \
  --child-receipt <cleanup-receipt.json> \
  --child-receipt <redelivery-activate-receipt.json> \
  --child-receipt <final-status-receipt.json>"

make governance-console-proposal-target \
  ACTION=verify-proposal-target-commissioning
```

The first command rereads the OOS application with the dedicated Console
caller, proves canonical Proposal acknowledgement, proves the human-reviewed
Studio merge and both bounded capture files from current `main`, validates the
negative matrix and lifecycle sequence, and records only value-free evidence.
Lifecycle receipts retain the policy's activation revision for Prototype
Studio even after the successful application advances Studio `main`. The
canonical target proof separately records and validates the current post-merge
Studio revision; commissioning must not reinterpret the earlier lifecycle
receipts as if they were created after that authority change.
The second command is non-mutating and is the exact operating evidence-profile
entry point.
