# OpenProject Product Integration

This directory captures the platform-specific integration contract for
OpenProject Community Edition on the local `k3s` cluster.

OpenProject is treated here as an internal supporting product or service that
uses the shared platform control plane.

## What This Directory Covers

- runtime contract
- delivery ART contract
- dependencies
- secrets and non-secret config expectations
- visibility and operating checks

## What It Does Not Cover

- upstream OpenProject source code
- generic platform bootstrap
- OpenClaw-specific host-control automation

## Current Product Shape

OpenProject is currently:

- deployed and reconciled by Argo CD
- packaged through the official upstream Helm chart
- backed by a standalone platform-managed PostgreSQL service plus local app
  storage
- exposed through the existing Windows localhost-friendly operator access model

## Current Workflow Maturity

OpenProject is currently `platform-integrated`, not `fully governed` in the
same end-to-end sense as OpenClaw.

That means:

- product docs, access guidance, scripts, and platform-managed deployment exist
- the product has a real operating model on the shared platform
- but it does not currently have a distinct OpenClaw-style source-to-stage-to-
  prod workflow with separate rehearsal and promotion gates

The highest implemented endpoint today is the platform-managed OpenProject
runtime on the local cluster plus its documented operator procedures.

## Start Here

- [AGENTS.md](AGENTS.md)
- [runtime-contract.md](runtime-contract.md)
- [idea-backlog-contract.md](idea-backlog-contract.md)
- [delivery-art-contract.md](delivery-art-contract.md)
- [dependencies.md](dependencies.md)
- [secrets-and-config.md](secrets-and-config.md)
- [visibility-and-operations.md](visibility-and-operations.md)
- [runbooks/access-openproject.md](runbooks/access-openproject.md)
- [scripts/README.md](scripts/README.md)
- [runbooks/README.md](runbooks/README.md)

Product-specific operational procedures such as backup and restore also live
under `runbooks/` and should not be added back to shared platform runbooks.
