# OpenProject Runbooks

This directory contains OpenProject-specific platform runbooks.

These runbooks describe the OpenProject product integration on the platform.
They are not shared platform procedures.

Within `Workspace Delivery ART`, the current runbook set covers the PM²
initiative layer plus the supported SAFe execution surface, including PI
views, PI objectives, team/iteration planning summaries, system-demo and
inspect-and-adapt recording, ART risks, blockers, parking, completion
evidence, closeout, and ART-quality validation.

## Runbook Lanes At A Glance

```mermaid
flowchart LR
    Access[Access and product runtime]
    Proposals[Proposal plane]
    Startup[ART startup and read path]
    Mutations[ART mutation and execution control]
    Evidence[Review, evidence, and closeout]
    Runtime[Runtime hygiene and production controls]

    Access --> Proposals
    Access --> Startup
    Proposals --> Startup
    Startup --> Mutations
    Mutations --> Evidence
    Evidence --> Runtime
```

Read this as operator workflow families:

- `access-openproject.md` gets you to the product and admin surface.
- `configure-idea-backlog.md` and `manage-proposal-to-delivery.md` live on the
  proposal side.
- `show-delivery-initiatives.md`, `show-delivery-active-front.md`, and
  `check-delivery-art-quality.md` are the ART startup path.
- the create, update, move, blocker, dependency, parking, and governance
  runbooks are the execution-control lane.
- PI review, system-demo, inspect-and-adapt, closeout readiness, and closeout
  itself are the evidence lane.
- backup, uninstall, identity provisioning, and clean-start guidance remain
  runtime and hygiene controls around the workflow model.

## Runbooks

- [access-openproject.md](access-openproject.md)
- [bootstrap-openproject.md](bootstrap-openproject.md)
- [configure-idea-backlog.md](configure-idea-backlog.md)
- [configure-delivery-art.md](configure-delivery-art.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [update-delivery-initiative.md](update-delivery-initiative.md)
- [record-system-demo.md](record-system-demo.md)
- [record-inspect-and-adapt.md](record-inspect-and-adapt.md)
- [create-delivery-work-item.md](create-delivery-work-item.md)
- [bulk-update-delivery-work-items.md](bulk-update-delivery-work-items.md)
- [move-delivery-work-item.md](move-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [complete-delivery-work-item.md](complete-delivery-work-item.md)
- [manage-delivery-dependency.md](manage-delivery-dependency.md)
- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [show-delivery-active-front.md](show-delivery-active-front.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [show-pi-objectives.md](show-pi-objectives.md)
- [record-pi-review.md](record-pi-review.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [manage-delivery-parking.md](manage-delivery-parking.md)
- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [prepare-production-clean-start.md](prepare-production-clean-start.md)
- [provision-operator-orchestration-identity.md](provision-operator-orchestration-identity.md)
- [openproject-backup-restore.md](openproject-backup-restore.md)
- [uninstall-openproject.md](uninstall-openproject.md)
