# ADR-001: Source Of Truth Boundaries

## Status

Accepted

## Context

Recent production fixes exposed repeated ambiguity about where changes belong:

- Telegram logic defects
- bundled runtime composition defects
- workspace template drift under `~/.openclaw`
- prod image pinning and promotion steps

Without a documented ownership model, fixes risk landing in the wrong repository or remaining as live-only drift.

## Decision

Define source-of-truth boundaries as follows:

- `openclaw-telegram-enhanced`
  - owns Telegram/plugin behavior and Telegram-side tests
- `openclaw-isolated-deployment`
  - owns bundled runtime composition and tracked workspace templates required inside the deployed image
- `platform-engineering`
  - owns environment pins, source-bundle validation, build workflow policy, digest recording, and Argo promotion
- host/runtime environment
  - owns Windows, WSL, k3s, Ollama, firewall, and portproxy state

## Consequences

### Positive

- fixes land at the correct layer
- prod rebuilds become reproducible
- validators can enforce cross-repo contracts
- runtime drift is easier to distinguish from source defects

### Negative

- some incidents require coordinated changes across multiple repositories
- operators must classify incidents before fixing them

## Rules derived from this ADR

- do not treat `~/.openclaw` edits as final unless that path is explicitly source-controlled
- do not place deployment workspace templates in the Telegram plugin repo
- do not place prod artifact metadata in the deployment repo
- do not resolve environment drift with a rebuild-only mindset
