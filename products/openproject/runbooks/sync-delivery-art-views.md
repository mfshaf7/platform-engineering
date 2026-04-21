# Sync Delivery ART Views

## Purpose

Reconcile the operator-visible SAFe plus PM² views for `Workspace Delivery ART`
on the current OpenProject runtime.

Use this when:

- the delivery ART already exists
- board access or saved delivery views drifted
- you need to add or refresh Program Increment versions
- you want the canonical PM² initiative register and execution boards

## Current Truth

On this platform, OpenProject Community Edition does not expose the native
enterprise `status` and `version` action-board types.

So the supported delivery-art surface here is:

- `board_view` enabled on `workspace-delivery-art`
- a basic-board `PM² Initiative Register`
- a basic-board `ART Execution Kanban`
- a basic-board `Program Increment Planning` when PI versions exist
- a basic-board `PI Objectives` when PI versions exist
- a basic-board `ART Risk Register`
- project versions used as the declared SAFe Program Increment set
- `Target PI` used as the writable work-item placement field for PI planning
  and PI objective views

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
- recreates the managed query set for PM², execution status, PI planning,
  PI objectives, and ART risks
- recreates the managed board set from those queries

## Expected Outcome

The delivery project exposes these operator views:

- `PM² Initiative Register`
- `ART Execution Kanban`
- `Program Increment Planning` when PI versions exist
- `PI Objectives` when PI versions exist
- `ART Risk Register`

The managed query set also exists for:

- `PM² Initiatives`
- `ART Execution / <status>`
- `PI Planning / <version>`
- `PI Objectives / <version>`
- `ART Risks / <roam-state>`

## Verification

In the OpenProject UI:

- open project `Workspace Delivery ART`
- confirm the `Boards` menu is present
- confirm board `PM² Initiative Register` exists
- confirm board `ART Execution Kanban` exists
- if PI versions exist, confirm board `Program Increment Planning` exists
- if PI versions exist, confirm board `PI Objectives` exists
- confirm board `ART Risk Register` exists

Shell check:

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "project = Project.find_by!(identifier: \"workspace-delivery-art\"); puts({enabled_modules: project.enabled_module_names, boards: Boards::Grid.where(project: project).pluck(:name), versions: project.versions.with_status_open.pluck(:name)}.to_json)"'
```

## Related References

- [configure-delivery-art.md](configure-delivery-art.md)
- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
