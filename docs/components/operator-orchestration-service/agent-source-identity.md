# Agent Source Identity

## Role And State

Platform owns credential custody and token issuance for the product-neutral
Agent source role. The first profile is `Agent Gary` (`agent-gary`), transported
by the selected-repository GitHub App principal
`mfshaf7-agent-gary[bot]`. The authoritative Platform definition is
[agent-source-identity.yaml](../../../security/agent-source-identity.yaml).

The original commissioning definition retains its historical inactive marker;
it is not the current OOS activation authority. Use the accepted OOS source
workflow and exact runtime/Security bindings for normal source availability.
Engineering delivery below does not itself authorize source actions, review,
approval, merge or default-branch writes.

## Console Credential Effects — Staged Producer

The existing authenticated Platform operation provider now implements source
for `agent-source.issue`, `agent-source.renew`, and `agent-source.revoke`.
Do not operate this extension until dependent OOS/Console consumers and final
exact Security acceptance have been commissioned together. Current source
implementation is not a claim of Console availability.

Use the existing `/v1/console-operations/commands` envelope, source-version
binding, authenticated OOS caller and exact operator approval. Capability ID
equals the source action; the Platform subject remains the configured runtime
profile. `input` contains exactly `source_intent` and nullable `session_id`.
The closed intent contains `schema_version: 1`, `purpose: ordinary-source`,
`intent_id`, authenticated `caller_id`, accountable `operator_id`, `subject`,
`source_start_digest`, exact `repository`, integer `repository_id` and
`installation_id`, `landing_unit_id`, non-default `branch`, exact40hex
`fetched_base`, `human_reviewer_id` and timezone-qualified `expires_at`.
The required `supersedes_intent_digest` is null initially. An explicitly approved
recovery generation names its exact revoked predecessor instead; it keeps the
logical Landing Unit and may rotate branch/base under a new source-start digest.
Platform requires the same canonical subject, operator and repository, no live
predecessor projection and no unresolved predecessor issuance. Old command
receipts remain readable; old revoke/retry cannot mutate a successor credential.
This is normal recovery, not a new ART item or a permanently unusable Landing Unit.

Delivery subject: exactly `kind: delivery`, actual `work_item_ref`
(`work-item-<id>`) and canonical `snapshot_digest`. Prototype subject: exactly
`kind: prototype`, actual `prototype_id`, matching `registry_ref`, independent
exact40hex `registry_revision`, bounded `repo://` `source_ref` and exact40hex
`source_revision`. These fields are bindings, not proof of canonical existence:
OOS must resolve and authorize the actual record and source-start input before
dispatch. Model/browser-selected requests must not pass through as trusted OOS
assertions. An absent session is correct before Delivery work start. Once OOS
binds the actual session, a different or absent session cannot renew it.

Issue creates no branch/worktree. Replaying its command returns the same
historical receipt without minting. A missing or near-expiry projection needs
an explicit renew command under the same still-approved intent; current tokens
are reused. Revoke also works before issue or after approval expiry. It writes
a durable non-secret tombstone first; a delayed issue cannot reopen it. A new
command cannot change intent, Landing Unit, repository, base or branch. Generic
worker cancellation is unavailable for these effects: use exact revoke.

Cold recovery reads the original command through the existing by-command API.
If a process died after projecting the credential, retry recovers it without
minting. If issuance may have happened without a recoverable projection, the
provider reports `platform_source_issuance_uncertain` with `retry_after` at the
maximum token lifetime. Revoke records the stop immediately but does not claim
an unobserved provider token was revoked: it reports
`platform_source_revocation_expiry_pending` until that bound expires. Keep the
same command/intent; do not manufacture another source request as recovery.
Known custody/provider preflight failures before minting can retry immediately;
the uncertainty wait applies only after the actual mint phase was entered.

Success returns only a `source_credential` receipt inside the existing terminal
receipt: binding/digest/expiry, subject/session, action/outcome and receipt digest.
Keys/tokens never enter the journal, logs, OOS responses, browser or model.
The token is repository-scoped at GitHub; branch/base and approval expiry are
OOS/executor controls, not native GitHub token restrictions. OOS must recheck
them at work start and every source action and revoke on terminal close/cancel.
Read-only status/preflight never invokes these actions. Bootstrap, organization
admission and App permissions are separate; this ordinary-source producer does
not authorize them. See [ADR-029](../../decisions/adr/ADR-029-source-intent-credential-effects.md).

## Primary Operator Path

The Make target uses the cataloged persistent Vault operator endpoint
`http://127.0.0.1:32200` by default. Use the documented `vault-ui`
port-forward at `http://127.0.0.1:8220` only when the primary endpoint is
unavailable from the current WSL network mode. `AGENT_SOURCE_VAULT_ADDR` is
reserved for that verified fallback or another explicitly verified
environment; do not start a port-forward for normal operation while the
primary endpoint is healthy.

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

This issuer's admitted target set is the active governed owner repositories
recorded in the Workspace Governance repository inventory. The Platform
definition resolves that inventory to exact provider repository ids and fails
closed when the two sets differ. Retired, proposed, external and unclassified
repositories remain outside this issuance set; an App installation elsewhere
is not source admission. Each issued token exposes
exactly one admitted repository and only Metadata read, Contents write, Pull
requests write, and Checks read. Platform does not accept a repository from
the current directory, remote URL, branch name, or ambient `gh` session.

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

The initial source boundary is
[Agent Gary Source Identity Boundary Review](https://github.com/mfshaf7/security-architecture/blob/e622b2a53c171a47e89dcafb0391cbc53650ee9c/docs/reviews/components/2026-09-11-agent-gary-source-identity-boundary.md).
The earlier closure-repository extension is recorded by the
[Closure Source Scope Review](https://github.com/mfshaf7/security-architecture/blob/7523dd5cce3bbac5fd35e4d21c8b7ad8d65b757a/docs/reviews/components/2026-09-13-agent-gary-closure-source-scope.md):
provider installation, one-repository tokens, and protected `main` remain
mandatory. ART `#1166` retains the final Security activation decision for the
workspace-wide lifecycle context; this Platform commissioning does not replace
that gate.
