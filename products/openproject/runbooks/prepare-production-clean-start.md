# Prepare Production Clean Start

## Purpose

This runbook defines the clean-start gate that must pass before the
proposal-to-delivery workflow is activated in a real production plane.

Use it when:

- a new production OpenProject proposal plane is being activated
- a new production delivery ART plane is being activated
- you need to prove the runtime is not already contaminated by rehearsal data

## Rule

Production must start clean at initial activation time.

That means:

- no dev-integration smoke records
- no governed stage rehearsal records
- no manually fabricated test proposals
- no rehearsal-created delivery epics
- no copied rehearsal backlinks
- no upstream demo projects

The first real production proposal and the first real production delivery epic
must both be real operator work, not migrated test data.

After activation, production keeps its own production history. This gate does
not mean the production plane must remain empty forever. It means the plane
must not inherit dev-integration, stage, or other rehearsal data as if that
data were real production history.

## Verification Command

Run from `platform-engineering/`:

```bash
make openproject-verify-clean-start REQUIRE_EMPTY=true
```

For initial activation, this check verifies:

- project `workspace-proposals` exists
- project `workspace-delivery-art` exists
- both projects contain zero work packages
- upstream demo projects are absent

It also reports the current version counts for both projects so the operator
can see whether PI scaffolding exists, but version counts are not treated as
data pollution by the current check.

After the production plane is genuinely live, do not use this gate as an
ongoing emptiness requirement. At that point, real production proposals and
delivery items are expected to exist.

## Required Outcome

The check must report:

- `clean_start_ready: true`

If it reports `false`, do not treat the environment as production-ready for the
proposal-to-delivery workflow.

## If The Check Fails

Do not push forward with production activation.

First determine why data exists:

- real historical import intentionally loaded
- rehearsal or smoke data leaked into the candidate production plane
- upstream demo projects were not removed
- canonical proposal or delivery project provisioning never completed

Only these are acceptable next moves:

- rebuild or reprovision the candidate production plane from a clean baseline
- import vetted real historical records with explicit provenance
- explicitly defer activation until the plane is clean

Do not relabel rehearsal data as production history.

## Recommended Activation Sequence

1. Bootstrap the OpenProject runtime and secret delivery:
   - `make openproject-apply`
2. Provision the canonical proposal plane:
   - `make openproject-configure-idea-backlog`
3. Provision the canonical delivery plane:
   - `make openproject-configure-delivery-art`
4. Provision broker delivery-plane access:
   - `make openproject-provision-operator-orchestration-delivery-access`
5. Verify clean start:
   - `make openproject-verify-clean-start REQUIRE_EMPTY=true`
6. Only after the check passes, allow real production proposals and delivery
   consumption to begin

## Related References

- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [bootstrap-openproject.md](bootstrap-openproject.md)
- [configure-idea-backlog.md](configure-idea-backlog.md)
- [configure-delivery-art.md](configure-delivery-art.md)
- [idea-backlog-contract.md](../idea-backlog-contract.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
