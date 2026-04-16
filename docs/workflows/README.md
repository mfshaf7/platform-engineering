# Workflow Catalog

This directory documents the GitHub workflow entrypoints used by the platform.

Use it when the question is:

- which workflow should an operator run
- what approvals or environment gates apply
- what a workflow changes
- what evidence a workflow should produce

## Current Workflows

| Workflow | Doc | Trigger | Main outcome |
| --- | --- | --- | --- |
| `build-and-validate.yaml` | [build-and-validate.md](build-and-validate.md) | push, pull_request | validates shared repo shape and configuration |
| `build-gateway-image.yaml` | [build-gateway-image.md](build-gateway-image.md) | manual | builds and pushes the OpenClaw gateway image |
| `build-telegram-overlay-image.yaml` | [build-telegram-overlay-image.md](build-telegram-overlay-image.md) | manual | builds and pushes the stage-only OpenClaw Telegram overlay experiment image |
| `confirm-stage-promotion-readiness.yaml` | [confirm-stage-promotion-readiness.md](confirm-stage-promotion-readiness.md) | manual | records stage verification evidence and approval for the current candidate |
| `drift-check.yaml` | [drift-check.md](drift-check.md) | schedule, manual | checks for missing platform overlays and app manifests |
| `manage-stage-environment.yaml` | [manage-stage-environment.md](manage-stage-environment.md) | manual | resumes or suspends stage desired state |
| `promote-environment.yaml` | [promote-environment.md](promote-environment.md) | manual | creates a prod promotion branch from an approved stage candidate |
| `security-posture.yaml` | [security-posture.md](security-posture.md) | pull_request, manual | validates minimum repo security posture docs and controls |

## Rule

Each workflow in `.github/workflows/` should have a same-named document here.

Use [TEMPLATE.md](TEMPLATE.md) when adding a new workflow.
