# Bulk Update Delivery Work Items

## Purpose

Apply one reviewable batch of day-to-day execution updates to multiple delivery
work items in `Workspace Delivery ART`.

Use this when you need to rescope or rebalance a slice of work without clicking
 through each item manually, for example:

- move several items into a new `Iteration`
- reassign a set of tasks to a different `Delivery Team`
- adjust PI placement or assignees across multiple items
- update schedule and progress fields in one controlled batch

This is the supported operator surface for multi-record execution updates below
the top-level initiative.

## Batch File Shape

Use a JSON file with this schema:

```json
{
  "schema_version": 1,
  "updates": [
    {
      "target_work_package_id": 40,
      "status": "in-progress",
      "target_pi": "PI-2026-02",
      "delivery_team": "Platform Architecture",
      "iteration": "Iteration 2",
      "start_date": "2026-04-21",
      "due_date": "2026-04-25",
      "estimated_work": 8,
      "remaining_work": 5,
      "percent_complete": 40,
      "work_note": "Rescoped into Iteration 2 after PI replanning."
    },
    {
      "target_work_package_id": 41,
      "clear_target_pi": true,
      "clear_assignee": true,
      "clear_due_date": true,
      "clear_remaining_work": true
    }
  ]
}
```

Supported update keys:

- `target_work_package_id`
- `status`
- `target_pi`
- `clear_target_pi`
- `assignee_login`
- `clear_assignee`
- `description`
- `clear_description`
- `work_note`
- `start_date`
- `clear_start_date`
- `due_date`
- `clear_due_date`
- `estimated_work`
- `clear_estimated_work`
- `remaining_work`
- `clear_remaining_work`
- `percent_complete`
- all supported structured SAFe execution fields from
  [update-delivery-work-item.md](update-delivery-work-item.md)

Restrictions:

- `status=done` is intentionally rejected
- use [complete-delivery-work-item.md](complete-delivery-work-item.md) for
  evidence-backed completion
- mutually exclusive clear/set pairs are rejected in the same entry

## Command

Run from `platform-engineering/`:

```bash
make openproject-bulk-update-delivery-work-items \
  DELIVERY_WORK_ITEM_UPDATE_FILE=/abs/path/work-item-updates.json
```

Optional fields:

- `OPENPROJECT_DELIVERY_PI_NAMES`
  Use this when the batch introduces a new PI version that should also be
  reflected in the managed delivery-art views.

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-bulk-update-delivery-work-items \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  DELIVERY_WORK_ITEM_UPDATE_FILE=/abs/path/work-item-updates.json
```

## Expected Outcome

- each requested work item is updated through one supported batch surface
- the command prints which work items changed and which ones were already in the
  requested state
- delivery-art views are refreshed after the batch

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- inspect the affected work items
- confirm the intended `Status`, `Target PI`, `Delivery Team`, `Iteration`,
  schedule, and progress values are present

For larger rescopes, also compare the output of:

- [show-delivery-planning.md](show-delivery-planning.md)
- [show-delivery-execution.md](show-delivery-execution.md)

## Related References

- [update-delivery-work-item.md](update-delivery-work-item.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
