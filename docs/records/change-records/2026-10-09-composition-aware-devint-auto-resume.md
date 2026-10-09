# Composition-Aware Dev-Integration Auto-Resume

## Summary

After a WSL restart, the accepted-idea-delivery auto-resume unit replayed a
standalone profile `up` while `refinement-catalog` owned the active runtime.
The profile guard correctly refused that command, but the unit retried it
indefinitely and never recreated the volatile Delivery source-executor path.

## Classification

- local `dev-integration` recovery-control regression
- host/runtime drift repair plus shared runner source fix
- no stage or production change

## Ownership

- durable fix: `platform-engineering`
- affected profile and source executor: `operator-orchestration-service`
- improvement record: `workspace-governance`

## Root Cause

The generated unit always encoded `up --profile <id>`, even when the successful
launch was a runtime composition. The unit also disabled systemd start limiting,
so a fail-closed ownership rejection became an unlimited retry loop.

## Source Changes

- `scripts/dev_integration_auto_resume.py` preserves the owning composition in
  the recovery command and bounds failed retries.
- `scripts/dev_integration.py` supplies the active composition and every
  explicit source override to the unit renderer.
- focused and full dev-integration runner tests cover both standalone and
  composition-owned recovery.

## Artifact And Deployment Evidence

No production artifact or governed environment changed. The local runtime was
recovered through `make devint-up COMPOSITION=refinement-catalog` with existing
single-writer Delivery mutation admission. Durable rollout requires the merged
Platform revision to regenerate the user unit through that same operator
surface.

## Live Verification

The recovery command restored CGG, WGCF, the governed AI gateway, Temporal,
OpenProject, OOS, the Delivery view synchronizer, and the Delivery source
executor. OOS returned work-session status for Delivery item `#1247` at source
commit `1bfe4dee23cc7169acc5ca766d3b5f38ce59435b` after recovery.

## Follow-Up Actions

- merge the Platform maintenance PR after CI and human review
- rerun the composition `up` from merged `main` to regenerate the user unit
- verify the installed unit targets `refinement-catalog` and carries bounded
  retry controls without exposing credentials
- close the linked improvement candidate after that live readback
