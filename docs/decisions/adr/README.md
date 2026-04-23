# Architecture Decision Records

This directory stores Architecture Decision Records for shared platform design.

## Current ADRs

- [ADR-001-source-of-truth-boundaries.md](ADR-001-source-of-truth-boundaries.md)
- [ADR-002-runtime-workspace-materialization.md](ADR-002-runtime-workspace-materialization.md)
- [ADR-003-vault-transit-auto-unseal.md](ADR-003-vault-transit-auto-unseal.md)
- [ADR-004-transit-vault-temporary-windows-trust-root.md](ADR-004-transit-vault-temporary-windows-trust-root.md)
- [ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md](ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md)
- [ADR-006-retire-legacy-openclaw-architecture-owner.md](ADR-006-retire-legacy-openclaw-architecture-owner.md)
- [ADR-007-post-promotion-prod-smoke-evidence.md](ADR-007-post-promotion-prod-smoke-evidence.md)
- [ADR-008-stage-telegram-overlay-experiment.md](ADR-008-stage-telegram-overlay-experiment.md)
- [ADR-009-governed-telegram-overlay-artifact-lane.md](ADR-009-governed-telegram-overlay-artifact-lane.md)
- [ADR-010-governed-openclaw-prod-lifecycle.md](ADR-010-governed-openclaw-prod-lifecycle.md)
- [ADR-011-governed-runtime-lifecycle-standard.md](ADR-011-governed-runtime-lifecycle-standard.md)
- [ADR-012-governed-ai-access-plane-and-model-profiles.md](ADR-012-governed-ai-access-plane-and-model-profiles.md)
- [ADR-013-openproject-proposal-to-delivery-split-and-one-art-model.md](ADR-013-openproject-proposal-to-delivery-split-and-one-art-model.md)
- [ADR-014-governed-full-platform-runtime-drill-and-restore.md](ADR-014-governed-full-platform-runtime-drill-and-restore.md)
- [ADR-015-platform-observability-baseline-and-overlay-model.md](ADR-015-platform-observability-baseline-and-overlay-model.md)

## Rules

- ADRs document design decisions, not rollout evidence.
- If an ADR was implemented in governed stage, prod, or host-owned live state,
  link the corresponding change record.
- Superseded ADRs should say so clearly near the top.
- New ADRs should use [TEMPLATE.md](TEMPLATE.md).
