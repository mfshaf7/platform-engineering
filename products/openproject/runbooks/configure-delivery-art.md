# Configure OpenProject Delivery ART

## Purpose

Provision the canonical OpenProject delivery plane for accepted ideas that move
out of `Workspace Proposals`.

This configures:

- the `workspace-delivery-art` project
- the delivery work package types
- the delivery execution statuses
- the project-scoped custom fields used for PM² governance, origin backlinks,
  and blocker tracking

This baseline does not precreate Program Increment versions or Kanban boards.
Those remain part of the delivery operating model, but they are added when the
accepted-idea-delivery flow is activated for real work.

## Preconditions

- OpenProject is healthy on the local platform
- the proposal backlog model already exists:
  - `make openproject-configure-idea-backlog`

## Command

```bash
make openproject-configure-delivery-art
```

## Expected Outcome

- `workspace-delivery-art` exists
- delivery types exist:
  - `Epic`
  - `Feature`
  - `Enabler`
  - `User story`
  - `Task`
  - `Milestone`
- delivery statuses exist:
  - `new`
  - `ready`
  - `in-progress`
  - `blocked`
  - `done`
- project-scoped custom fields exist for:
  - `PM² Phase`
  - `Origin Idea Ref`
  - `Sponsor`
  - `Business Objective`
  - `Success Criteria`
  - `Target PI`
  - blocker statement, ownership, decision, and review tracking

## Verification

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Project.where(identifier: [\"workspace-delivery-art\"]).pluck(:identifier, :name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Type.where(name: [\"Epic\", \"Feature\", \"Enabler\", \"User story\", \"Task\", \"Milestone\"]).pluck(:name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Status.where(name: [\"new\", \"ready\", \"in-progress\", \"blocked\", \"done\"]).pluck(:name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "project = Project.find_by!(identifier: \"workspace-delivery-art\"); puts project.work_package_custom_fields.order(:position).pluck(:name).inspect"'
```

## Next Step

Once the delivery ART exists, grant the broker service identity access to both
the proposal and delivery projects:

```bash
export VAULT_TOKEN='...'
make openproject-provision-operator-orchestration-delivery-access
```
