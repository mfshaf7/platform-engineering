# ADR-008: Stage Telegram Overlay Experiment

## Status

- Superseded by ADR-009

## Context

Small Telegram-only fixes currently require rebuilding and redeploying the full
OpenClaw gateway image because the packaged Telegram runtime is delivered only
as part of the gateway artifact.

That is safe, but it makes minor stage-only Telegram fixes too expensive.

## Decision

Introduce a bounded stage-only Telegram overlay experiment:

- Telegram source still builds from the publishable allowlist in
  `openclaw-telegram-enhanced`
- `openclaw-runtime-distribution` owns packaging that allowlist into a separate
  Telegram overlay artifact
- `platform-engineering` pins the overlay artifact by digest in the stage
  contract
- the stage deployment mounts that artifact back onto `/app/extensions/telegram`
  through an init container and shared volume
- the experiment remains stage-only and blocks any `stage -> prod` promotion
  while active

## Why

This reduces the operational cost of small Telegram-only stage fixes without:

- reintroducing mutable runtime patching
- reviving unsupported same-id global Telegram overrides
- pretending the experiment is ready for prod before evidence exists

## Consequences

Positive:

- stage can rehearse small Telegram-only fixes without rebuilding the full
  gateway image
- the overlay artifact stays immutable and reviewable by digest
- the runtime seam remains owned by `openclaw-runtime-distribution`

Negative:

- stage now has an additional artifact path to govern
- the stage candidate model must expose the active overlay experiment
- prod promotion needs an explicit guard against an active stage overlay

## Alternatives Considered

- Keep rebuilding the full gateway image for every Telegram-only stage fix
  - safer by simplicity, but too operationally expensive for small Telegram-only
    stage changes
- Reintroduce a same-id global Telegram override under `/home/node/.openclaw`
  - rejected because the current runtime contract explicitly treats that path as
    unsupported and too drift-prone

## Follow-up

- prove the experiment on stage with real Telegram behavior
- completed in ADR-009, which graduates the pattern into a governed prod lane
