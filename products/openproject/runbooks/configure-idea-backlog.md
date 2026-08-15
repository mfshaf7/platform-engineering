# Configure OpenProject Idea Backlog

## Purpose

Provision the canonical OpenProject project model for captured ideas and
proposals.

This configures:

- the `workspace-proposals` project
- the proposal work package types
- the proposal workflow statuses
- the project-scoped work package custom fields

It also removes the upstream seeded demo projects so the OpenProject interface
starts from a clean baseline.

## Preconditions

- OpenProject is healthy on the local platform
- the operator accepts destructive removal of the upstream demo projects:
  - `demo-project`
  - `your-scrum-project`

## Command

```bash
make openproject-configure-idea-backlog
```

## Expected Outcome

- the two upstream demo projects are deleted
- `workspace-proposals` exists
- proposal types exist:
  - `Idea`
  - `Governance Proposal`
  - `Security Proposal`
  - `Product Proposal`
  - `Component Proposal`
- proposal statuses exist:
  - `captured`
  - `triaged`
  - `parked`
  - `owner-assigned`
  - `accepted`
  - `rejected`
  - `implemented`
  - `superseded`
- project-scoped custom fields exist for the backlog workflow
  - including the `Delivery Ref` backlink field used once accepted proposals
    are consumed into the separate ART project
  - including the non-searchable, non-filterable `Proposal Workflow State` text
    field governed by
    [`proposal-workflow-state.schema.json`](../proposal-workflow-state.schema.json)
- existing Proposal records remain unmodified; the provisioning operation does
  not fabricate workflow-state documents

## Verification

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Project.order(:id).pluck(:identifier, :name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Type.where(name: [\"Idea\", \"Governance Proposal\", \"Security Proposal\", \"Product Proposal\", \"Component Proposal\"]).pluck(:name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Status.where(name: [\"captured\", \"triaged\", \"parked\", \"owner-assigned\", \"accepted\", \"rejected\", \"implemented\", \"superseded\"]).pluck(:name).inspect"'
```

## Notes

- This runbook does not create the future automation user or API token yet.
- OpenProject remains the canonical backlog store; this workflow does not create
  Git artifacts directly.
- `operator-orchestration-service` must validate a workflow-state document
  against the product schema before writing it and must use the work package
  `lockVersion` as the optimistic-concurrency precondition.
