# Sync Delivery ART Views

## Purpose

Reconcile the operator-visible SAFe plus PM² views for `Workspace Delivery ART`
on the current OpenProject runtime.

Use this when:

- the delivery ART already exists
- board access or saved delivery views drifted
- you need to add or refresh Program Increment versions
- you want the canonical PM², execution, PI-objective, and risk boards

## Current Truth

On this platform, OpenProject Community Edition does not expose the native
enterprise `status` and `version` action-board types.

So the supported delivery-art surface here is:

- `board_view` enabled on `workspace-delivery-art`
- a generated project overview that explains the ART operating model
- a basic-board `ART Dashboard`
- a basic-board `PM² Phase Board`
- a basic-board `ART Execution Kanban`
- a basic-board `PI Objectives` when PI versions exist
- a basic-board `ART Risk Register`
- project versions used as the declared SAFe Program Increment set
- `Target PI` used as the writable work-item placement field for PI objective
  lanes and the planning read-model surfaces
- `Execution Classification` used to distinguish `Business`, `Enabler`, and
  `Improvement` work on `Feature` and `User story` without reintroducing a
  fake structural `Enabler` type

This is the strongest supported SAFe plus PM² operator surface in the current
packaged runtime.

## Command

Without explicit PI versions:

```bash
make openproject-sync-delivery-art-views
```

With explicit PI versions:

```bash
make openproject-sync-delivery-art-views PI_NAMES="PI-2026-02,PI-2026-03"
```

The command:

- enables `board_view` on `workspace-delivery-art`
- creates or reuses project versions for the supplied PI names
- also reuses any PI names already present through actual `Target PI` values on
  delivery work items
- refreshes the generated project overview content for the ART home
- normalizes managed ART list custom-field storage to the current OpenProject
  custom-option id form before rebuilding managed queries and boards
- recreates the managed query set for PM² phase, execution status, PI
  objectives, and ART risks
- recreates the managed board set from those queries

## Expected Outcome

The delivery project exposes these operator views:

- `ART Dashboard`
- `PM² Phase Board`
- `ART Execution Kanban`
- `PI Objectives` when PI versions exist
- `ART Risk Register`

Planning remains a supported read-model/report surface through:

- `show-delivery-planning`
- `show-delivery-initiatives`
- `show-pi-objectives`

The managed query set also exists for:

- `PM² Phase / <phase>`
- `ART Execution / <status>`
- `PI Objectives / <version> / <committed-or-stretch>`
- `ART Risks / <roam-state>`

The managed execution board includes a dedicated `parked` lane so deferred open
work stays visible in the OpenProject UI alongside the active execution flow.

## Verification

In the OpenProject UI:

- open project `Workspace Delivery ART`
- confirm the overview explains the ART operating model and main board surfaces
- confirm the `Boards` menu is present
- confirm board `ART Dashboard` exists
- confirm board `PM² Phase Board` exists
- confirm board `ART Execution Kanban` exists
- if PI versions exist, confirm board `PI Objectives` exists
- confirm board `ART Risk Register` exists

Shell check:

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "project = Project.find_by!(identifier: \"workspace-delivery-art\"); puts({enabled_modules: project.enabled_module_names, boards: Boards::Grid.where(project: project).pluck(:name), versions: project.versions.with_status_open.pluck(:name)}.to_json)"'
```

## Related References

- [configure-delivery-art.md](configure-delivery-art.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
