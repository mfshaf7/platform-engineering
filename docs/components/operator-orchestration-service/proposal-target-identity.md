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
  --source-revision governance-operations-console=e993e9a55b80a24dcab4b96b8291ece822c8dd0f \
  --source-revision operator-orchestration-service=287e840ddbda584f2b85556952e0179dd7543748 \
  --source-revision security-architecture=e136d6f7d543e0dde78a1959fa299e989efecfe1 \
  --source-revision workspace-prototype-studio=eab7af0c44de2e76eb381bf06447105ce3a28863 \
  --receipt <private-receipt-path>"

make proposal-target-identity ACTION=deliver ARGS="\
  --app-id <app-id> \
  --installation-id <installation-id> \
  --private-key-file <private-0600-pem> \
  --caller-id platform-engineering \
  --source-revision governance-operations-console=e993e9a55b80a24dcab4b96b8291ece822c8dd0f \
  --source-revision operator-orchestration-service=287e840ddbda584f2b85556952e0179dd7543748 \
  --source-revision security-architecture=e136d6f7d543e0dde78a1959fa299e989efecfe1 \
  --source-revision workspace-prototype-studio=eab7af0c44de2e76eb381bf06447105ce3a28863 \
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
