# Governed Change Model

## Purpose

This standard defines how production-impacting changes move from incident to verified deployment in the Platform-Core environment.

The goal is to prevent:

- live-only fixes that disappear on rebuild
- cluster-only drift that bypasses source control
- image changes without immutable provenance
- repeated incidents caused by missing ownership or missing validation

## Core rule

No production fix is considered complete unless it is resolved at the owning layer and, when applicable, promoted through the normal artifact and Argo path.

Emergency runtime edits are allowed only as temporary containment. They must be:

1. explicitly identified as temporary
2. traced back to an owning source repository
3. replaced by a governed source change as soon as practical

## Ownership boundaries

### `openclaw-telegram-enhanced`

Owns:

- Telegram/plugin behavior
- Telegram routing contracts
- Telegram-specific tests

Does not own:

- deployment workspace materialization
- image composition
- environment pinning or promotion

### `openclaw-isolated-deployment`

Owns:

- bundled runtime composition
- deployment-specific runtime content
- tracked workspace templates that must exist inside the bundled image
- image assembly inputs

Does not own:

- environment-specific digest promotion
- Argo deployment state

### `platform-engineering`

Owns:

- environment pins
- build workflow policy
- source-bundle validators
- immutable digest recording
- Argo promotion and deployment metadata
- operator runbooks and governance standards

Does not own:

- Telegram plugin implementation details
- deployment workspace content templates beyond validation and pinning

### Host and environment runtime

Owns:

- Windows, WSL, k3s, portproxy, firewall, Ollama, and other live platform services

This layer is not image-baked. It must be managed through runbooks and verified live.

## Incident classification

Every issue must be classified before fixing it:

1. App/plugin source bug
2. Deployment/artifact composition bug
3. Environment metadata or pin drift
4. Host/environment drift

The classification determines the owning repository and required promotion path.

## Required change flow

For any production-impacting fix:

1. Reproduce and verify the live failure.
2. Identify the owning layer.
3. Make the source change in the owning repository.
4. Add a guardrail:
   - test
   - validator
   - build check
   - ownership doc
5. Push the change.
6. Rebuild the immutable artifact if the issue affects the runtime image.
7. Record the new digest and source pins in `platform-engineering`.
8. Let Argo deploy the new revision.
9. Verify live:
   - app health
   - image digest
   - logs
   - one functional check

## Disallowed end states

These are not acceptable final fixes:

- editing `~/.openclaw` and stopping there
- patching a pod or container manually and stopping there
- changing runtime state without identifying an owning repo
- using mutable tags in place of recorded digests for prod
- promoting a digest without validating the source bundle

## Required evidence for completion

Every production fix should leave enough evidence to answer:

- what failed
- what layer owned the fix
- what commits changed
- what image digest was built
- what Argo revision deployed
- what live checks proved the result

## Environment-only drift

Some incidents are not source defects. Examples:

- Windows portproxy drift
- Ollama listener availability
- firewall rules
- service state in WSL or Windows

These are allowed to remain outside the image path only when:

- the owning layer is clearly the host environment
- the fix is captured in a runbook
- the verification command is documented

## Enforcement

This standard is enforced through:

- pinned source SHAs
- source-bundle validation in CI
- immutable digest recording
- Argo-managed deployment
- post-change live verification

## Practical decision rule

If a fix would be lost by rebuilding the gateway image or rehydrating the runtime, it is not governed yet.
