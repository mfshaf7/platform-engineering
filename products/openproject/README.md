# OpenProject Product Integration

This directory captures the platform-specific integration contract for
OpenProject Community Edition on the local `k3s` cluster.

OpenProject is treated here as an internal supporting product or service that
uses the shared platform control plane.

## What This Directory Covers

- runtime contract
- proposal backlog and delivery ART project contracts
- dependencies
- secrets and non-secret config expectations
- visibility and operating checks
- product-scoped operator scripts and runbooks for the OpenProject workflow
  model

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

The canonical OpenProject workflow model now has two distinct planes:

- `Workspace Proposals` for intake and proposal triage
- `Workspace Delivery ART` for accepted work that moves into tracked delivery

Both remain platform-managed operator flows inside this product directory. They
do not imply a separate OpenClaw-style governed promotion lane.

## Delivery Work-State Truth

When a serious initiative is already running inside `Workspace Delivery ART`,
start from the ART before doing repo work.

Truth split:

- `Workspace Delivery ART` = work-state truth
- owner repos = implementation and design truth
- `workspace-governance` = workspace-control truth

That means:

- new sessions should open the active initiative summary first
- chat and handoff notes are secondary context, not the official work queue
- meaningful uncovered work must be reconciled into the ART or routed to the
  correct alternate system of record

Out-of-coverage routing:

- same initiative: add a new `Feature` or `Task` under the active `Epic`
- new initiative: route through `Workspace Proposals`
- repeated process or control miss: route to
  `workspace-governance/reviews/improvement-candidates/`
- security or trust-boundary judgment: route through
  `security-architecture` and reflect any blocking impact in the ART
- pure owner-repo maintenance outside the initiative: track it in the owner
  repo only

Inside `Workspace Delivery ART`, the current operator model is PM²-governed at
the initiative layer and SAFe-aligned at the execution layer, including:

- PI versions
- `PI Objective`, `Feature`, `Enabler`, `User story`, `Task`, `Milestone`, and
  `Risk` work-item types
- PI-objective business-value tracking
- WSJF prioritization fields
- ROAM risk tracking
- team and iteration planning summaries
- explicit system-demo and inspect-and-adapt recording workflows
- completion-evidence-backed execution and closeout workflows

## Start Here

- [AGENTS.md](AGENTS.md)
- [runtime-contract.md](runtime-contract.md)
- [idea-backlog-contract.md](idea-backlog-contract.md)
- [delivery-art-contract.md](delivery-art-contract.md)
- [dependencies.md](dependencies.md)
- [secrets-and-config.md](secrets-and-config.md)
- [visibility-and-operations.md](visibility-and-operations.md)
- [runbooks/access-openproject.md](runbooks/access-openproject.md)
- [runbooks/show-delivery-initiatives.md](runbooks/show-delivery-initiatives.md)
- [runbooks/show-delivery-active-front.md](runbooks/show-delivery-active-front.md)
- [runbooks/check-delivery-art-quality.md](runbooks/check-delivery-art-quality.md)
- [runbooks/manage-proposal-to-delivery.md](runbooks/manage-proposal-to-delivery.md)
- [runbooks/start-delivery-execution.md](runbooks/start-delivery-execution.md)
- [runbooks/create-delivery-work-item.md](runbooks/create-delivery-work-item.md)
- [runbooks/bulk-update-delivery-work-items.md](runbooks/bulk-update-delivery-work-items.md)
- [runbooks/move-delivery-work-item.md](runbooks/move-delivery-work-item.md)
- [runbooks/update-delivery-work-item.md](runbooks/update-delivery-work-item.md)
- [runbooks/complete-delivery-work-item.md](runbooks/complete-delivery-work-item.md)
- [runbooks/manage-delivery-dependency.md](runbooks/manage-delivery-dependency.md)
- [runbooks/show-delivery-execution.md](runbooks/show-delivery-execution.md)
- [runbooks/show-delivery-planning.md](runbooks/show-delivery-planning.md)
- [runbooks/show-pi-objectives.md](runbooks/show-pi-objectives.md)
- [runbooks/record-pi-review.md](runbooks/record-pi-review.md)
- [runbooks/check-delivery-closeout-readiness.md](runbooks/check-delivery-closeout-readiness.md)
- [runbooks/close-delivery-initiative.md](runbooks/close-delivery-initiative.md)
- [runbooks/sync-delivery-art-views.md](runbooks/sync-delivery-art-views.md)
- [runbooks/update-delivery-initiative.md](runbooks/update-delivery-initiative.md)
- [runbooks/record-system-demo.md](runbooks/record-system-demo.md)
- [runbooks/record-inspect-and-adapt.md](runbooks/record-inspect-and-adapt.md)
- [runbooks/manage-delivery-blocker.md](runbooks/manage-delivery-blocker.md)
- [runbooks/manage-delivery-parking.md](runbooks/manage-delivery-parking.md)
- [runbooks/prepare-production-clean-start.md](runbooks/prepare-production-clean-start.md)
- [scripts/README.md](scripts/README.md)
- [runbooks/README.md](runbooks/README.md)

Product-specific operational procedures such as backup and restore also live
under `runbooks/` and should not be added back to shared platform runbooks.
