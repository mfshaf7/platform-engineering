# ADR-009: Governed Telegram Overlay Artifact Lane

## Status

- Accepted

## Supersedes

- [ADR-008-stage-telegram-overlay-experiment.md](ADR-008-stage-telegram-overlay-experiment.md)

## Context

ADR-008 proved that small Telegram-only fixes could be delivered as a separate
immutable overlay artifact on stage without rebuilding the full gateway image.

That stage proof showed real operational value:

- faster Telegram repair cycles on an already qualified OpenClaw base
- no return to mutable runtime patching
- no revival of unsupported same-id user-home Telegram overrides

The remaining gap was governance. Stage-only proof is not enough if the same
artifact lane is going to shape prod behavior.

## Decision

Graduate the Telegram overlay into a governed delivery lane with these rules:

- the overlay remains a separate immutable artifact built from the
  `openclaw-telegram-enhanced` publishable payload through
  `openclaw-runtime-distribution`
- the lane is allowed only on a platform-qualified OpenClaw base image
- `platform-engineering` records:
  - overlay source commit
  - overlay image digest
  - qualified base image
- stage must qualify the exact overlay digest on the current base image before
  any prod use
- `stage -> prod` promotion may carry the overlay only when prod uses the same
  qualified base image as the approved stage candidate
- prod still requires post-promotion smoke or UAT evidence

## Why

This keeps the fast Telegram repair path without weakening the enterprise
delivery model.

The overlay lane stays:

- immutable
- digest-pinned
- reviewable in Git
- tied to a concrete base line
- reversible through the same governed promotion path

## Consequences

Positive:

- small Telegram-only fixes no longer force a full gateway rebuild on an
  already qualified base line
- stage and prod can attest both the gateway artifact and the Telegram overlay
  artifact
- rollback stays Git-managed because both artifacts are carried in the
  environment contract

Negative:

- OpenClaw now has a dual-artifact delivery path to govern
- every new base line still requires separate qualification before the overlay
  lane is reused
- security review and visibility surfaces must expose the overlay state, digest,
  and qualified base image

## Alternatives Considered

- keep the overlay permanently stage-only
  - simpler, but it keeps small Telegram prod fixes operationally expensive
- make Telegram fully mutable at runtime
  - rejected because it breaks attestation, rollback clarity, and Git-managed
    release authority

## Follow-up

- keep the base gateway lane as the qualification path for new OpenClaw base
  images
- treat the overlay lane as the fast Telegram artifact path on top of that
  qualified base
- maintain post-promotion prod smoke/UAT as a separate governed evidence step
