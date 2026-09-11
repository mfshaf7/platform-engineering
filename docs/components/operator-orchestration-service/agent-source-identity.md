# Agent Source Identity

## Role And State

Platform owns credential custody and token issuance for the product-neutral
Agent source role. The first profile is `Agent Gary` (`agent-gary`), transported
by the selected-repository GitHub App principal
`mfshaf7-agent-gary[bot]`. The authoritative Platform definition is
[agent-source-identity.yaml](../../../security/agent-source-identity.yaml).

Normal OOS consumption remains disabled until ART #1137. This Platform surface
commissions the provider identity and can create an inactive, exact Landing
Unit projection for verification; it does not authorize OOS source actions,
review, approval, merge, or default-branch writes.

## Primary Operator Path

```bash
make agent-source-identity ACTION=validate

make agent-source-identity ACTION=commission ARGS="\
  --bootstrap-private-key-file <temporary-0600-pem> \
  --retire-bootstrap-key \
  --receipt <commission-receipt.json>"

make agent-source-identity ACTION=deliver ARGS="\
  --landing-unit-id <landing-unit-id> \
  --repository mfshaf7/<approved-repository> \
  --branch <non-default-branch> \
  --fetched-base <40-character-commit> \
  --human-reviewer-id mfshaf7 \
  --receipt <delivery-receipt.json>"

make agent-source-identity ACTION=revoke ARGS="\
  --landing-unit-id <landing-unit-id> \
  --repository mfshaf7/<approved-repository> \
  --receipt <revocation-receipt.json>"

make agent-source-identity ACTION=suspend ARGS="\
  --receipt <suspension-receipt.json>"
```

`commission` imports the temporary App private key into the exact Vault path,
reads it back through the Platform boundary, verifies the App and installation,
and proves every approved repository separately. Every proof token is limited
to one repository and revoked before success is recorded. A normal bootstrap
commission refuses to continue unless the temporary key is retired after the
Vault and provider checks pass.

`deliver` mints one token for one approved repository and one immutable Landing
Unit binding. The projection is an atomically replaced `0600` credential under
the operator's `XDG_RUNTIME_DIR`; it does not survive a host restart. Rotation
revokes the prior token before publishing the replacement while holding the
projection lock. OOS #1137 must make the source executor take the same lock and
re-read the credential for every bounded action.

`suspend` records the issuance stop before revoking projected tokens. `revoke`
is idempotent for one exact Landing Unit. Resume requires another successful
commission with `--resume-issuance`; removing the suspension marker by hand is
not an operator procedure.

## Authority And Least Privilege

The App installation is selected over only the five repositories recorded in
the contract. Each issued token exposes exactly one of them and only Metadata
read, Contents write, Pull requests write, and Checks read. Platform does not
accept a repository from the current directory, remote URL, branch name, or
ambient `gh` session.

Agent Gary authors and pushes an admitted non-default review branch and may
open or update its pull request after #1137. `mfshaf7` remains the accountable
human reviewer, approver, and merger. Agent credentials cannot approve, merge,
push `main`, administer repositories, alter rulesets, delete branches or
repositories, broaden installation scope, or fall back to human credentials.

## Custody, Restart, And Evidence

The private key is read only from the Platform Vault path declared by the
contract. Direct private-key files are accepted only by the sandbox test path.
The runtime projection contains a short-lived installation token, so it is
local, ephemeral, operator-private, and excluded from source, logs, receipts,
Review Packets, browser responses, and model context.

Receipts retain identity, App, installation, repository, Landing Unit, branch,
fetched base, expiry, human reviewer, action, and outcome metadata without key
or token values. A restarted executor must obtain or observe a newly delivered
credential and reconcile source truth; no durable work-session record may be
used to recover an old token.

The accepted Security boundary is
[Agent Gary Source Identity Boundary Review](https://github.com/mfshaf7/security-architecture/blob/e622b2a53c171a47e89dcafb0391cbc53650ee9c/docs/reviews/components/2026-09-11-agent-gary-source-identity-boundary.md).
