# Configure OpenProject Delivery ART

## Purpose

Provision the canonical OpenProject delivery plane for accepted ideas that move
out of `Workspace Proposals`.

This configures:

- the `workspace-delivery-art` project
- the generated project overview content for the ART landing page
- the delivery work package types
- the delivery execution statuses
- the project-scoped custom fields used for PM² governance, SAFe planning,
  origin backlinks, blocker governance, parking, WSJF, and ROAM risk tracking
- the delivery-art board module plus the managed PM², execution, PI objective,
  and risk board presets

Program Increment versions are created when you supply `PI_NAMES` or when real
delivery records already carry `Target PI` values.

## Preconditions

- OpenProject is healthy on the local platform
- the proposal backlog model already exists:
  - `make openproject-configure-idea-backlog`

## Command

```bash
make openproject-configure-delivery-art
```

To create or refresh explicit PI versions in the same run:

```bash
make openproject-configure-delivery-art PI_NAMES="PI-2026-02,PI-2026-03"
```

## Expected Outcome

- `workspace-delivery-art` exists
- delivery types exist:
  - `Epic`
  - `PI Objective`
  - `Feature`
  - `User story`
  - `Defect`
  - `Task`
  - `Milestone`
  - `Risk`
- delivery statuses exist:
  - `new`
  - `ready`
  - `in-progress`
  - `blocked`
  - `parked`
  - `retired`
  - `done`
- project-scoped custom fields exist for:
  - initiative-only `Epic` governance:
    - `PM² Phase`
    - `Origin Idea Ref`
    - `Sponsor`
    - `Business Objective`
    - `Success Criteria`
    - `System Demo Evidence`
    - `Inspect & Adapt Actions`
    - `NFR Category`
  - `Target PI`
  - SAFe execution fields:
    - `Delivery Team`
    - `Iteration`
    - `Execution Classification`
    - `Acceptance Criteria`
    - `Definition of Ready`
    - `Definition of Done`
    - `NFR Category`
  - PI objective fields:
    - `PI Objective Type`
    - `PI Objective Review Outcome`
    - `Planned Business Value`
    - `Actual Business Value`
  - prioritization fields:
    - `WSJF User-Business Value`
    - `WSJF Time Criticality`
    - `WSJF Risk Reduction / Opportunity Enablement`
    - `WSJF Job Size`
    - `WSJF Score`
  - risk fields:
    - `ROAM State`
    - `Risk Owner`
    - `Risk Review Date`
    - `Risk Disposition`
  - blocker statement, ownership, decision, and review tracking
  - parking decision, reason, deferred review tracking, and `Retirement Reason`
- initiative-only governance fields are hidden from child work-item forms by
  type scoping
- the `Boards` project module is enabled
- managed board `ART Dashboard` exists
- managed board `PM² Phase Board` exists with a dedicated `Retired` terminal lane
- managed board `ART Execution Kanban` exists
- managed board `PI Objectives` exists when PI versions are present
- managed board `ART Risk Register` exists

## Verification

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Project.where(identifier: [\"workspace-delivery-art\"]).pluck(:identifier, :name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Type.where(name: [\"Epic\", \"PI Objective\", \"Feature\", \"User story\", \"Defect\", \"Task\", \"Milestone\", \"Risk\"]).pluck(:name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "puts Status.where(name: [\"new\", \"ready\", \"in-progress\", \"blocked\", \"parked\", \"retired\", \"done\"]).pluck(:name).inspect"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "project = Project.find_by!(identifier: \"workspace-delivery-art\"); puts({custom_fields: project.work_package_custom_fields.order(:position).pluck(:name), enabled_modules: project.enabled_module_names, boards: Boards::Grid.where(project: project).pluck(:name), versions: project.versions.with_status_open.pluck(:name)}.to_json)"'
```

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "field = WorkPackageCustomField.find_by!(name: \"NFR Category\"); puts field.types.order(:name).pluck(:name).inspect"'
```

## Next Step

Once the delivery ART exists, converge the assignable repo-owner identities for
the canonical delivery plane:

```bash
export VAULT_TOKEN='...'
make openproject-provision-delivery-art-identities
```

To refresh the delivery views later without reprovisioning the whole project:

```bash
make openproject-sync-delivery-art-views PI_NAMES="PI-2026-02,PI-2026-03"
```
