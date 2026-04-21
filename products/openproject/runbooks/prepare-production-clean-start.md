# Prepare Production Clean Start

## Purpose

This runbook defines the production-activation hygiene gate that must pass
before the proposal-to-delivery workflow is activated in a real production
plane.

Use it when:

- a new production OpenProject proposal plane is being activated
- a new production delivery ART plane is being activated
- you need to prove the runtime is not contaminated by rehearsal data

## Rule

Production activation must be noise-free and provenance-safe.

That means:

- no dev-integration smoke records
- no governed stage rehearsal records
- no manually fabricated test proposals
- no rehearsal-created delivery epics
- no copied rehearsal backlinks
- no upstream demo projects

What is allowed:

- real production history already created in that plane
- explicitly curated historical imports with clear provenance
- an explicitly approved promoted ART baseline, including the current validated
  ART history when it is being carried into production deliberately

What is not allowed:

- dev-integration or stage-originated records represented as production history
  without explicit approval and provenance
- copied rehearsal backlinks or fabricated governance records
- upstream demo content left in place as if it were real work

An empty plane is still a valid and stricter initial-activation choice, but it
is no longer the only valid production shape when the existing records are
already noise-free and provenance-safe.

Important distinction:

- promoted ART baseline history is allowed when it has been deliberately
  approved as the production starting point
- disposable smoke, demo, and rehearsal-only records are not

## Verification Command

Run from `platform-engineering/`:

```bash
make openproject-verify-clean-start
```

Default production activation verification checks:

- project `workspace-proposals` exists
- project `workspace-delivery-art` exists
- upstream demo projects are absent

It also reports:

- current work-package counts in both projects
- current version counts in both projects
- whether existing records are present and therefore require operator
  provenance review

The command does not automatically decide whether existing records are valid
production baseline history. That judgment still requires explicit operator
approval and provenance evidence.

Use the stricter empty-plane mode only when you explicitly want first
activation from an empty production plane:

```bash
make openproject-verify-clean-start REQUIRE_EMPTY=true
```

That stricter mode additionally requires:

- both canonical projects contain zero work packages

After the production plane is genuinely live, do not use this gate as an
ongoing emptiness requirement. At that point, real production proposals and
delivery items are expected to exist.

## Required Outcome

The default activation-hygiene check must report:

- `production_activation_hygiene_ready: true`

If you intentionally require an empty first activation, it must also report:

- `empty_plane_ready: true`

If the required readiness field reports `false`, do not treat the environment
as production-ready for the proposal-to-delivery workflow.

## If The Check Fails

Do not push forward with production activation.

First determine why data exists:

- real historical import intentionally loaded
- real production history already exists and is being kept
- an approved promoted ART baseline is being carried into production
- rehearsal or smoke data leaked into the candidate production plane
- upstream demo projects were not removed
- canonical proposal or delivery project provisioning never completed

Only these are acceptable next moves:

- keep the plane and document that the existing records are real production
  history, vetted imports, or an approved promoted ART baseline with explicit
  provenance
- rebuild or reprovision the candidate production plane from a clean baseline
  when the existing records are noisy
- import vetted real historical records with explicit provenance
- explicitly record the promoted ART baseline provenance before activation
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
5. Verify production activation hygiene:
   - `make openproject-verify-clean-start`
   - optionally require an empty first activation:
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
