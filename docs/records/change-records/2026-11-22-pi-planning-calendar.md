# PI Planning Calendar Control

## Summary

The OpenProject Catalog adapter saves a PI and its dated iteration windows in
one native transaction. PI Planning and the Catalog use the same saved
calendar. Existing labels and assignments remain available for readback.

## Classification

Existing Delivery calendar maintenance in dev-integration. This source change
is part of the PI Planning batch and carries no deployment evidence.

## Ownership

Platform owns the native OpenProject Catalog adapter and standardization
runner. The Platform Landing Unit is `pi-planning-calendar-platform-20261122`
with decision `feature_single_landing_unit`. The broker owns planning and
write eligibility, and the Console owns presentation.

## Root Cause

Standalone Catalog iteration edits could create labels without dated windows.
Other surfaces interpreted those labels as a schedule. Standardization also
filled unset work-item iterations without a reviewed PI plan.

## Source Changes

The Catalog derives the inclusive PI end and all iteration windows from the
accepted start and cadence. It rejects overlaps and keeps exact replay tied
to the saved receipt. Dating an existing PI keeps established label identities
and work-item assignments. The standardization runner leaves unset iterations
for PI Planning. See the [Catalog contract](../../../products/openproject/catalog-control/README.md).

## Artifact And Deployment Evidence

Source and Catalog contract only. The exact owner revisions require the
normal composed Security review and activation before deployment.

## Host Or Runtime Recovery

The normal release path retains the previous accepted composition. A saved
calendar or work-item decision requires its own reviewed correction.

## Live Verification

Disposable OpenProject proved calendar persistence, exact replay, overlap
denial, and reconciliation with iteration labels and assignments retained.
The current working ART dates and assignments were outside that test.

## Follow-Up

Activate with the matching broker and Console. Inspect catalog and planning
readback before an operator decides to date any historical PI.
