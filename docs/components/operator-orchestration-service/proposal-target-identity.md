# Proposal Target Identity

This is the primary Platform operator surface for commissioning and operating
the dedicated Proposal Target GitHub App in local `dev-integration`. It belongs
to Delivery ART work item `#1236`; it does not require or create another ART
child.

The identity is restricted to the single public repository
`mfshaf7/workspace-prototype-studio`. OOS may create only deterministic
`proposal-target/<digest>` review branches whose changes remain under
`records/prototype-captures/**`. The App cannot approve or merge. The human
reviewer owns exact-head approval and merge.

## Create And Install The App Once

Create a personal GitHub App named for Proposal Target with:

- repository selection: only `workspace-prototype-studio`;
- repository permissions: Contents `Read and write`, Pull requests `Read and
  write`, Checks `Read-only`, and Metadata `Read-only`;
- no webhook and no subscribed events; and
- no permission to bypass the repository ruleset.

Generate one private key, install the App only on the selected repository, and
record the numeric App and installation ids. The private key is bootstrap
input only. Import it into the Platform Vault path declared in
`security/proposal-target-identity.yaml`; do not copy it into OOS, source,
receipts, logs, or ART evidence.

## Validate And Deliver

Use a clean checkout at every exact source revision declared by the contract.
The `--source-revision` set is closed: extra, missing, or different revisions
are rejected.

```bash
make proposal-target-identity ACTION=validate

make proposal-target-identity ACTION=commission ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --private-key-file <private-0600-pem> \
  --caller-id platform-engineering \
  --source-revision governance-operations-console=d66411f128c3fd2f21ac274f620352977966fecd \
  --source-revision operator-orchestration-service=0e935029327c3195f7ad1026c6f450f4b32c52dd \
  --source-revision security-architecture=add3b405cffe87d158c65edec1d24cf33ea2def8 \
  --source-revision workspace-prototype-studio=4066ea5ba5a68ab7ab12acc7fc395897e1ae6c3f \
  --receipt <private-receipt-path>"

make proposal-target-identity ACTION=deliver ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --private-key-file <private-0600-pem> \
  --caller-id platform-engineering \
  --source-revision governance-operations-console=d66411f128c3fd2f21ac274f620352977966fecd \
  --source-revision operator-orchestration-service=0e935029327c3195f7ad1026c6f450f4b32c52dd \
  --source-revision security-architecture=add3b405cffe87d158c65edec1d24cf33ea2def8 \
  --source-revision workspace-prototype-studio=4066ea5ba5a68ab7ab12acc7fc395897e1ae6c3f \
  --session-manifest <workspace>/.dev-integration/accepted-idea-delivery/<operator>/current-session.yaml \
  --workspace-root <workspace> \
  --receipt <private-receipt-path>"
```

Delivery validates the provider App and installation, requests an exact-one-
repository short-lived token, mounts it read-only, mounts Prototype Studio
read-only, creates a private persistent state directory, and enables only
`OOS_PROPOSAL_TARGET_APPLICATION_ENABLED`. It never injects a browser
credential or grants Console direct GitHub authority.

## Suspend, Revoke, And Recover

Use `suspend` to deny new target applications while retaining the projected
token and durable OOS state. Use `revoke` to revoke the projected token and
remove the Proposal Target environment, Secret, and mounts. Neither action
deletes source, a merged capture, Git history, or review evidence.

After a host or pod restart, run `deliver` again. Delivery replaces the token,
forces the OOS rollout, confirms the new session binding, then revokes the
prior token. Normal availability is proven only after the Console loopback path
passes current positive and negative owner-backed checks and rollback is
followed by a clean redelivery.
