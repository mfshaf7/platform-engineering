# Manage Proposal To Delivery

## Purpose

This is the primary operator workflow for moving an already accepted proposal
from `Workspace Proposals` into `Workspace Delivery ART` and then verifying the
delivery record in OpenProject.

Use this runbook when:

- a proposal is already accepted
- the work now needs execution tracking in the delivery plane
- you need the current supported operator path, not the underlying contracts

## Current Truth

- `Workspace Proposals` is the proposal plane
- `Workspace Delivery ART` is the execution plane
- the consume step is currently broker-owned and internal-only
- there is no Telegram delivery-management command and no OpenProject UI button
  for consume yet
- the current supported operator path is:
  - inspect and approve in OpenProject and the broker-owned workflow
  - run the product-scoped consume helper
  - verify the result in the OpenProject UI

This is a platform-managed workflow on the local cluster. It is not a separate
OpenClaw-style product promotion lane.

## Before You Start

Confirm these are already true:

- OpenProject is reachable:
  - `make openproject-access`
- the proposal backlog exists:
  - `make openproject-configure-idea-backlog`
- the delivery ART exists:
  - `make openproject-configure-delivery-art`
- the broker service identity has delivery-project access:
  - `make openproject-provision-operator-orchestration-delivery-access`

## Step 1: Review The Source Proposal

In the OpenProject UI:

- open project `Workspace Proposals`
- open the source proposal
- verify the proposal status is `accepted`
- verify the proposal title, captured body, triage summary, and decision notes
  are complete enough to become the delivery initiative

Before consume, the source proposal should either:

- have no `Delivery Ref` yet
- or already point to the correct delivery record when you are rechecking an
  idempotent consume result

## Step 2: Consume The Accepted Proposal

Run the product-scoped consume helper from `platform-engineering/`:

```bash
make openproject-consume-accepted-idea \
  IDEA_ID=idea-64 \
  TARGET_PI=PI-2026-02 \
  OPERATOR_ID=mfshaf7 \
  OPERATOR_HANDLE=mfshaf7
```

Required input:

- `IDEA_ID`

Recommended input:

- `TARGET_PI`
- `OPERATOR_ID`
- `OPERATOR_HANDLE`

The helper:

- verifies the source idea is already `accepted`
- verifies project `workspace-delivery-art` exists
- calls the broker-owned internal `POST /v1/ideas/{idea_id}/consume` route
- refreshes the managed delivery-art views after consume
- creates or reuses the matching PI version when `TARGET_PI` is supplied
- prints the resulting delivery ref and backlink summary as JSON

## Step 3: Verify The Result In OpenProject

In `Workspace Proposals`, confirm:

- the source proposal still has status `accepted`
- field `Delivery Ref` now points at the delivery record

In `Workspace Delivery ART`, confirm:

- a top-level `Epic` exists for the consumed proposal
- `Origin Idea Ref` equals the original broker idea id
- `PM² Phase` is set
- `Target PI` is set when you supplied one

To update the top-level delivery governance record after consume, use:

- [update-delivery-initiative.md](update-delivery-initiative.md)

Minimum backlink check:

- source proposal `Delivery Ref` equals the delivery record ref
- delivery record `Origin Idea Ref` equals the source broker idea id

## Step 4: Manage Execution In The Delivery Plane

Use the two planes differently:

- `Workspace Proposals`
  - proposal-of-record
  - stays at `accepted` while delivery is active
- `Workspace Delivery ART`
  - execution-of-record
  - carries the delivery hierarchy and execution statuses

Current delivery structure:

- top-level governance item:
  - `Epic`
- lower execution hierarchy:
  - `Feature`
  - `Enabler`
  - `User story`
  - `Task`
  - `Milestone`

Current execution statuses:

- `new`
- `ready`
- `in-progress`
- `blocked`
- `parked`
- `done`

To seed the first execution tree under a consumed delivery `Epic`, use:

- [start-delivery-execution.md](start-delivery-execution.md)

When the delivery `Epic` is complete and ready to move the source proposal to
`implemented`, use:

- [close-delivery-initiative.md](close-delivery-initiative.md)

## Where PM² Is In The UI

`PM²` is currently the governance overlay on the top-level delivery item.

In the UI today, look for these fields on the delivery `Epic`:

- `PM² Phase`
- `Sponsor`
- `Business Objective`
- `Success Criteria`
- `Target PI`

This is the current v1 form of PM² here:

- one top-level PM²-governed initiative
- one ART execution model below it
- board `PM² Initiative Register` as the PM² list surface
- board `ART Execution Kanban` as the execution status surface
- board `Program Increment Planning` when PI versions exist

Because the current runtime is OpenProject Community Edition, these are
implemented through basic board presets plus project versions, not the native
enterprise action-board types.

## Blockers And Impediments

When a delivery item is blocked, do not stop at status `blocked`.

Also record:

- `Blocker Statement`
- `Blocker Impact`
- `Blocker Owner`
- `Blocker Discovered On`
- `Blocker Decision Path`
  - `remove`
  - `workaround`
  - `accept-risk`
  - `defer`
- `Blocker Justification`
- `Blocker Follow-Up Owner`
- `Blocker Review Date`

Use the supported blocker command instead of manual field editing:

- [manage-delivery-blocker.md](manage-delivery-blocker.md)

When a delivery item is intentionally removed from active scope without
deletion, use the supported parking command instead of manual UI cleanup:

- [manage-delivery-parking.md](manage-delivery-parking.md)

## Production Clean-Start Rule

If this workflow is later activated in a real `prod` environment, the initial
production activation must start from a clean state.

That means:

- no dev-integration smoke records
- no governed stage rehearsal records
- no manually created test ideas or delivery epics
- no copied rehearsal backlinks
- no placeholder PI values or fake governance records carried over as if they
  were real delivery history

Required initial production baseline:

- proposal plane contains only real operator proposals or explicitly curated
  historical imports
- delivery plane contains no rehearsal-generated execution records
- the first production delivery `Epic` originates from a real accepted proposal
  in the production proposal plane

If you want seed data in production at all, import only vetted real records
with explicit provenance. Do not promote local or stage rehearsal data.

After the production plane is live, it should keep its own production history.
The clean-start rule only applies to the initial activation gate.

Before activating that production plane, run:

```bash
make openproject-verify-clean-start REQUIRE_EMPTY=true
```

## Related References

- [idea-backlog-contract.md](../idea-backlog-contract.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [configure-idea-backlog.md](configure-idea-backlog.md)
- [configure-delivery-art.md](configure-delivery-art.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [update-delivery-initiative.md](update-delivery-initiative.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [provision-operator-orchestration-identity.md](provision-operator-orchestration-identity.md)
- [`operator-orchestration-service/docs/contracts/accepted-idea-delivery-consumption-v1.md`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/contracts/accepted-idea-delivery-consumption-v1.md)
