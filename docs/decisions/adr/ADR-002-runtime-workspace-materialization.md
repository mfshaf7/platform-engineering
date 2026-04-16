# ADR-002: Runtime Workspace Materialization

## Status

Accepted

## Context

The `security-architecture` Telegram topic failed because the live runtime expected a dedicated workspace:

- `/home/node/.openclaw/workspace-security-architecture/AGENTS.md`
- `/home/node/.openclaw/workspace-security-architecture/skills/security-architecture/SKILL.md`

That workspace existed only as live state under `~/.openclaw` and was not tracked in source. This caused:

- unresolved skill filters
- generic bootstrap behavior in a specialized topic
- non-reproducible recovery

## Decision

Tracked deployment workspaces that must exist inside the runtime image will be
materialized from the active build/composition repo. For the current governed
stage/prod path, that repo is `openclaw-runtime-distribution`.

The image build is responsible for copying those templates into `/home/node/.openclaw/...` as part of the bundled artifact.

`platform-engineering` is responsible for validating that required templates are
present in the pinned build/composition repo before a build can succeed.

## Consequences

### Positive

- workspace behavior becomes reproducible across rebuilds
- runtime specialization is part of artifact provenance
- missing templates fail in CI rather than in production

### Negative

- the active build/composition repo now owns more runtime content than only Docker build glue
- new specialized workspaces require explicit template maintenance

## Current application

This ADR currently applies to:

- `workspace-security-architecture`

Additional deployment-owned workspaces should follow the same model if they are required for correct runtime behavior.
