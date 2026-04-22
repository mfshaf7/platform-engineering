# Start Delivery Execution

## Purpose

This is the primary operator workflow for turning a consumed delivery `Epic`
into a real execution tree inside `Workspace Delivery ART`.

Use it when:

- an accepted proposal is already consumed into the delivery plane
- the top-level `Epic` exists
- you want to seed the first execution slices under that `Epic`

## Current Truth

- `Workspace Proposals` stays the proposal-of-record
- `Workspace Delivery ART` is the execution-of-record
- the current execution-start path is operator-driven
- plan application is now broker-backed
- for ongoing serious delivery work, start from
  [show-delivery-initiatives.md](show-delivery-initiatives.md) and
  [check-delivery-art-quality.md](check-delivery-art-quality.md) before
  resuming implementation from repo code
- the current durable operator path is:
  - capture or consume the top-level `Epic`
  - prepare a JSON delivery plan
  - apply that plan to the target `Epic` through the broker-owned plan/apply
    route
  - verify the created execution tree in OpenProject

## Before You Start

Confirm these are already true:

- OpenProject is reachable:
  - `make openproject-access`
- the delivery ART exists:
  - `make openproject-configure-delivery-art`
- the target delivery `Epic` already exists in `Workspace Delivery ART`

For the current serious-project rehearsal in the persistent dev-integration lane, the target is
delivery record `#38`.

If the requested work is not already covered by the active ART:

- absorb it into the active work item only when it is a tiny same-slice patch
- otherwise add a new `Feature` or `Task` under the current `Epic`
- use `Workspace Proposals` instead when the work is really a different
  initiative

## Plan File Shape

Use a JSON plan file with this schema:

```json
{
  "schema_version": 1,
  "epic_updates": {
    "description": "Markdown summary of the execution objective and initial success criteria.",
    "pm2_phase": "Planning",
    "target_pi": "PI-2026-02",
    "sponsor": "mfshaf7",
    "business_objective": "Define the product and tenant split for the governed local-agent platform.",
    "success_criteria": "- Engine and tenant boundaries are recorded in source-backed design artifacts.",
    "system_demo_evidence": "PI-2026-02 system demo will validate the first broker-backed delivery workflow slice.",
    "inspect_and_adapt_actions": "- Capture process debt discovered while migrating workflow operations into the broker."
  },
  "items": [
    {
      "type": "PI Objective",
      "subject": "PI-2026-02 objective: establish the productized workflow boundary",
      "status": "ready",
      "target_pi": "PI-2026-02",
      "pi_objective_type": "Committed",
      "planned_business_value": 8,
      "acceptance_criteria": "- The first broker delivery-plane route is live in source and tracked in the ART."
    },
    {
      "type": "Feature",
      "subject": "Feature subject",
      "description": "Optional markdown description",
      "status": "ready",
      "target_pi": "PI-2026-02",
      "start_date": "2026-04-21",
      "due_date": "2026-04-25",
      "estimated_work": 8,
      "remaining_work": 8,
      "percent_complete": 0,
      "delivery_team": "Platform Architecture",
      "iteration": "Iteration 1",
      "acceptance_criteria": "- The feature outcome is explicit and verifiable.",
      "definition_of_ready": "- Source boundary and target owner are clear.",
      "definition_of_done": "- Delivery evidence is captured through the supported completion workflow.",
      "wsjf_user_business_value": 8,
      "wsjf_time_criticality": 6,
      "wsjf_rr_oe": 7,
      "wsjf_job_size": 5,
      "children": [
        {
          "type": "Task",
          "subject": "Task subject",
          "description": "Optional markdown description",
          "status": "new",
          "target_pi": "PI-2026-02",
          "start_date": "2026-04-21",
          "due_date": "2026-04-23",
          "estimated_work": 4,
          "remaining_work": 4,
          "percent_complete": 0,
          "delivery_team": "Platform Architecture",
          "iteration": "Iteration 1",
          "acceptance_criteria": "- The concrete task output is inspectable in source or OpenProject evidence."
        }
      ]
    },
    {
      "type": "Risk",
      "subject": "Risk subject",
      "status": "ready",
      "target_pi": "PI-2026-02",
      "roam_state": "Owned",
      "risk_owner": "mfshaf7",
      "risk_review_date": "2026-04-28",
      "risk_disposition": "Monitor whether direct platform-side OpenProject execution surfaces should be brokerized."
    }
  ]
}
```

Supported item fields:

- `type`
- `subject`
- `description`
- `status`
- `target_pi`
- `start_date`
- `due_date`
- `estimated_work`
- `remaining_work`
- `percent_complete`
- `delivery_team`
- `iteration`
- `acceptance_criteria`
- `definition_of_ready`
- `definition_of_done`
- `nfr_category`
- `pi_objective_type`
- `planned_business_value`
- `actual_business_value`
- `roam_state`
- `risk_owner`
- `risk_review_date`
- `risk_disposition`
- `wsjf_user_business_value`
- `wsjf_time_criticality`
- `wsjf_rr_oe`
- `wsjf_job_size`
- `children`

Supported `epic_updates` fields:

- `description`
- `status`
- `target_pi`
- `pm2_phase`
- `sponsor`
- `business_objective`
- `success_criteria`
- `system_demo_evidence`
- `inspect_and_adapt_actions`
- `nfr_category`

Current behavior:

- creates missing child work packages under the target `Epic`
- reuses an existing work package when `parent + type + subject` already match
- reconciles existing child work package `status`, `description`, and explicit
  `target_pi` when they are present in the plan
- reconciles schedule and progress fields when they are present in the plan
- reconciles the supported structured SAFe fields when they are present in the plan
- updates the target `Epic` PM² and initiative governance fields when explicitly provided
- sets created child work packages to the parent priority, or the OpenProject
  system default priority when the parent has none
- inherits the parent PI on newly created child work packages when the plan
  does not explicitly set `target_pi`
- synchronizes the `Target PI` custom field with PI version assignment on created
  and updated work packages
- computes `WSJF Score` automatically when WSJF component fields are provided
- can non-destructively reconcile missing direct children by parking them when
  `RECONCILE_MISSING=park` is supplied

After the first tree exists, use
[create-delivery-work-item.md](create-delivery-work-item.md) for incremental
decomposition instead of rebuilding a whole plan for one new child item.

## Command

Run from `platform-engineering/`:

```bash
make openproject-apply-delivery-plan \
  TARGET_EPIC_ID=38 \
  DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json
```

For the persistent `accepted-idea-delivery` dev-integration lane, also set the
OpenProject namespace override:

```bash
make openproject-apply-delivery-plan \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json
```

Backend boundary:

- `openproject-apply-delivery-plan` is a thin wrapper over
  `POST /v1/delivery-initiatives/{delivery_id}/plan/apply`
- the platform-owned view sync still runs after the broker call using the PI
  names present in the plan so PI-backed views stay aligned with the current
  delivery tree

Optional reconciliation fields:

- `RECONCILE_MISSING=ignore|park`
- `RECONCILE_DECISION=retire|defer`
- `RECONCILE_RETIREMENT_REASON=superseded|duplicate|invalid|absorbed|cancelled`
- `RECONCILE_REASON="..."`
- `RECONCILE_REVIEW_DATE=YYYY-MM-DD`

Recommended usage when a reapply should remove obsolete child items from active
scope without deleting them:

```bash
make openproject-apply-delivery-plan \
  TARGET_EPIC_ID=38 \
  DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json \
  RECONCILE_MISSING=park \
  RECONCILE_DECISION=retire \
  RECONCILE_RETIREMENT_REASON=superseded \
  RECONCILE_REASON="Removed by revised execution plan"
```

## Expected Outcome

- the target `Epic` remains the top-level delivery root
- the requested `Feature`, `Enabler`, `User story`, `Task`, or `Milestone`
  items exist under that `Epic`
- the command prints a JSON result showing:
  - the target `Epic`
  - created items
  - updated items
  - reused items
  - deferred items when `RECONCILE_DECISION=defer`
  - retired items when `RECONCILE_DECISION=retire`

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target `Epic`
- confirm the expected child work packages exist
- confirm the execution tree shape matches the plan

For the persistent `accepted-idea-delivery` dev-integration lane, keep the UI
open with:

```bash
make devint-access PROFILE=accepted-idea-delivery
```

For the current serious project rehearsal, verify that delivery `Epic #38`
contains the first execution slices for the deferred productization thread.

## Current Limitation

This execution-start path is intentionally narrow.

It does not yet provide:

- destructive reconciliation for obsolete child items that are no longer in the plan

When a child item is no longer active scope but should remain auditable, either:

- reapply the plan with `RECONCILE_MISSING=park`
- or park it directly through [manage-delivery-parking.md](manage-delivery-parking.md)

Type changes are now handled non-destructively through the same reconciliation
path: the new typed item is created from the plan and the obsolete unmatched
item can be deferred or retired during reconcile instead of being deleted
manually.

Use [close-delivery-initiative.md](close-delivery-initiative.md) when the top-level
delivery `Epic` is complete and the source proposal should move to
`implemented`.

Those should be expanded only after the execution-start path is proven useful.

## Related References

- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [update-delivery-initiative.md](update-delivery-initiative.md)
- [create-delivery-work-item.md](create-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [complete-delivery-work-item.md](complete-delivery-work-item.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [manage-delivery-parking.md](manage-delivery-parking.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [configure-delivery-art.md](configure-delivery-art.md)
