# Governed Change Model

## Purpose

This standard defines how production-impacting changes move from incident or
feature request to verified deployment in the Platform-Core environment.

The goal is to prevent:

- live-only fixes that disappear on rebuild
- cluster drift that bypasses source control
- image changes without immutable provenance
- operator workflows that depend on tribal knowledge
- documentation and evidence surfaces drifting away from live reality

## Core Rule

No production-impacting fix is complete unless it is resolved at the owning
layer and, when applicable, promoted through the normal artifact plus Argo path.

Emergency runtime edits are containment only. They must be:

1. explicitly identified as temporary
2. traced back to an owning repository or host owner path
3. replaced by a governed source or platform change
4. documented with enough evidence that another operator can understand what
   happened and what closed the gap

## Ownership Model

| Layer | Primary owner | Typical examples |
| --- | --- | --- |
| Product or integration source | `openclaw-telegram-enhanced`, `openclaw-host-bridge`, active plugin owner | Telegram behavior, host enforcement, plugin packaging |
| Runtime composition | `openclaw-runtime-distribution` | bundled runtime assembly, packaging inputs, distribution validation |
| Platform approval and rollout | `platform-engineering` | pins, digests, promotion, Argo reconciliation, host provisioning |
| Reference architecture | `openclaw-isolated-deployment` | model explanation, deployment rationale, reference copies |
| Security governance | `security-architecture` | standards, review criteria, risk framing, ADRs |
| Live host environment | WSL/Windows host owner path, captured by `platform-engineering` runbooks | systemd services, Windows tasks, firewall, port forwarding |

## Change Classification

Every issue should be classified before fixing it:

1. source defect
2. runtime composition defect
3. platform contract or promotion defect
4. live host or environment drift
5. security or trust-boundary governance gap

The classification determines:

- where the fix belongs
- which validations are required
- which docs must change
- what evidence is needed before declaring completion

## Required Change Flow

For production-impacting work:

1. Verify the live problem or requested behavior.
2. Identify the owning layer.
3. Patch the smallest correct owner surface.
4. Add or strengthen a durable control:
   - test
   - verifier
   - attestation path
   - runbook
   - standards update
5. Update the owner docs if behavior, visibility, or workflow changed.
6. Rebuild the runtime artifact if the change affects the gateway image.
7. Record the resulting approved SHAs and digest in `platform-engineering`.
8. Let Argo reconcile the environment.
9. Verify live:
   - platform health
   - deployed digest or host revision
   - logs or audit trail
   - at least one real functional check

## Documentation Rule

Documentation is part of the governed path.

When a change affects any of the following, the owning docs should change in the
same work:

- ownership or source of truth
- component workflow
- release or promotion flow
- health, audit, visibility, or attestation surfaces
- restart or recovery behavior
- operator commands or required validation

The minimum acceptable documentation surface is:

- repo README that explains ownership and workflow
- operator-facing runbook or architecture doc for the changed behavior
- platform or security standards update when the control model changed

## Required Evidence

Every production-impacting fix should leave enough evidence to answer:

- what failed or what changed
- which repository or host layer owned the fix
- which commits changed
- which image digest or live host revision was approved
- which platform revision recorded the approval
- which Argo revision or host runtime state applied it
- which live checks proved the outcome

## Disallowed End States

These are not acceptable final fixes:

- editing `~/.openclaw` or a running pod and stopping there
- changing runtime state without identifying an owning layer
- relying on a feature branch or dirty checkout without backporting to `main`
- shipping a new privileged behavior without documentation, audit expectations,
  and approval story
- leaving repo docs ambiguous after changing the live operating model

## Environment-Only Drift

Some incidents are legitimately host or environment owned, for example:

- WSL or Windows service state
- firewall or port-forward drift
- Windows Task Scheduler drift
- local host policy files or environment files

These may remain outside the image path only when:

- the host is the true owner
- the fix is captured in a runbook or provisioning path
- the verification path is documented
- the runtime can still be attested after repair

## Enforcement

This model is enforced through:

- pinned source SHAs
- deterministic artifact tagging
- source-bundle validation
- immutable digest recording
- Argo-managed reconciliation
- host provisioning playbooks
- live verification and change records

## Practical Decision Rule

If a fix would be lost by rebuilding the gateway image, reprovisioning the WSL
host stack, or reapplying the platform contract, it is not governed yet.
