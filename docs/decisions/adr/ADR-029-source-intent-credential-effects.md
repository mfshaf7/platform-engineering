# ADR-029: Source-intent credential effects through the existing Platform provider

## Status

Accepted design by the operator on 2026-10-18. Source implementation and final
Security/runtime acceptance are separate; this ADR does not activate a service.

## Context

The existing source executor correctly refuses missing or expired exact Gary
credentials. Its normal Console source-start path cannot deliver them itself:
the identity adapter reads projections and the engineering operator must run
Platform delivery before a work session exists. That is not Console-only
operation. Requiring an existing session to fix this would create a circular
prerequisite. Prototype authoring also must not invent a Delivery identity.

## Decision

Extend the existing authenticated Platform operation provider with exactly
`agent-source.issue`, `agent-source.renew` and `agent-source.revoke`. Reuse the
same Vault custody, App, repository allowlist, one-repository token issuer,
projection lock and ephemeral credential format. No new daemon, general shell,
App permission or installation selection is introduced.

OOS resolves the actual canonical Delivery or Prototype and approved prospective
source-start input before dispatch. Platform validates a closed explicit
subject, exact intent/start digest, caller/operator, repository/provider IDs,
Landing Unit, branch/base, reviewer and approval expiry. A real session may
bind once after start; it is not required or fabricated before issuance.
Platform command approval binds the entire input; OOS must not pass arbitrary
browser/model credential requests through this trusted caller boundary.

Existing private provider state retains non-secret immutable intent bindings,
command receipts and revocation tombstones across ephemeral projection loss.
Issue replay never silently renews. Explicit renewal reuses a current token or
rotates a near-expiry one through the same issuer. A lost acknowledgement after
atomic projection recovers without another mint. Uncertain unprojected issuance
does not remint or claim revocation: recovery waits for the issuer's maximum
token lifetime, with a machine-readable not-before time. Revocation persists
the tombstone before contacting the provider. Running credential operations are
not killed using generic cancel; cancel the source intent with explicit revoke.
Known custody failures before the actual mint remain immediately retryable.
An explicitly approved successor preserves its logical Landing Unit and binds
the exact revoked predecessor. Fresh authorization of unchanged, still-valid
canonical work may retain its start digest, branch and session; expiry alone
does not require invented source or branch churn. Actual source recovery binds
its changed canonical start digest and may rotate branch/base. Neither case is
automatic renewal after approval expiry: the new intent needs fresh explicit
operator approval, current OOS canonical verification and no unresolved prior
credential. The intent identity remains immutable.
Retain predecessor command history; late old commands cannot touch its successor.

Credentials are repository-scoped at GitHub, **not branch-scoped by GitHub**.
Branch/base, source-start and session restrictions are enforced by OOS and its
executor, plus existing native main protection and human review. OOS must check
approval expiry on every source action; provider token expiry alone is not
approval authority. Bootstrap remains a different purpose and is rejected here.

Separate the App owner from its two approved installation accounts. For normal
Console issuance, reuse the existing composition's canonical record reader:
one current immutable Inventory/Intake snapshot under the exact accepted WG
control revision and reviewed schemas. Preserve legacy owner provider IDs;
new owners require active Inventory provider coordinates and canonical promotion
lineage. Promotion atomically consumes the admitted Intake entry; its id,
version and digest remain in Inventory rather than a coexisting Intake record.
Repeat readback immediately before remote minting.
Do not hardcode every future product repository in Platform, accept an HTTP
inventory assertion, widen the selected installation set, or add another
freshness engine. Revocation uses retained exact intent/projection truth even
after admission/freshness is withdrawn. Engineering delivery remains the old
fixed-set recovery surface, not a bypass for proposed or unadmitted targets.

## Consequences

The Console can expose explicit approved credential effects without receiving
keys/tokens or requiring an engineering delivery step. Status/preflight remain
read-only. This producer alone is not that completed capability: OOS canonical
resolution, its source-action expiry checks, Console controls and exact final
Security acceptance must land and commission coherently before use.

Hold Studio/WG control merges until dependent changes are prepared: the active
record refresher observes their remote main independently. Final source pins
use actual merged commits. Retain the accepted composition for rollback; revoke
only owned credentials and preserve requests, receipts and source history.

Source and operating evidence are recorded in
[the authoring change record](../../records/change-records/2026-10-18-console-source-authoring.md).
The primary operator/API surface remains
[Agent source identity](../../components/operator-orchestration-service/agent-source-identity.md).

## Alternatives Considered

- Continue engineering-only delivery: fails the accepted Console-only outcome.
- Mint in Console/OOS: moves key custody across the existing Platform boundary.
- Mint during status/preflight: disguises a privileged mutation as diagnosis.
- A separate daemon or generic mint API: unnecessary authority and lifecycle.
- Require a session first: contradicts current source-start credential gating.
