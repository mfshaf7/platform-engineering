# Dev-Integration Operator-Login Recovery

## Summary

- Date: 2026-09-07
- Short title: profile-declared operator-login recovery
- Environment: local dev-integration
- Severity: runtime resilience correction

## Classification

- Type: shared platform runner correction
- User-facing impact: an opted-in persistent profile can reconstruct its
  volatile runtime paths and declared host services after the operator logs in
  following a host or WSL restart.

## Ownership

- Owning repo or layer: `platform-engineering`
- Consumer repo: `operator-orchestration-service`
- Related ADR: existing dev-integration profile and declared host-service
  contracts; no new runtime authority is introduced.

## Root Cause

- Immediate failure: a restart removed the profile's private runtime directory
  and terminated host services while persistent Kubernetes state survived.
- Actual root cause: the shared runner could reconcile a profile only after a
  manual `up`; it had no opt-in login recovery policy.
- Why it escaped earlier controls: host-service supervision covered lifecycle
  after `up`, but not reconstruction after the host session ended.

## Source Changes

- Add `runtime.resume_policy` with a default of `manual` and an
  `operator-login` option restricted to persistent profiles.
- Generate one secret-free user-systemd unit that replays the existing shared
  `up` path with exact source paths and the command search path proven by the
  successful manual launch.
- Disable and remove the unit after a successful `down` or `reset`.
- Add unit rendering, lifecycle, and profile-contract tests plus operator
  guidance.

## Artifact And Deployment Evidence

- Build workflow run: not applicable to this host-side runner.
- Published image tag: None.
- Published digest: None.
- Recorded prod revision: None.
- Argo application revision: None.

## Host Or Runtime Recovery

- Required host/runtime action: run one successful profile `up` after the
  source change lands; later operator logins invoke the generated unit.
- Why it was environment drift instead of source defect: the interruption is
  expected host lifecycle, but automatic reconstruction was missing from the
  source contract.
- Recovery command or procedure: use the normal shared dev-integration `up`,
  `status`, `down`, and `reset` entrypoints.

## Live Verification

- App health: verify through the normal profile status command.
- Deployed image: unchanged.
- Pod: reconciled by the existing profile `up` implementation.
- Functional verification: simulate loss of the volatile runtime and host
  processes, start the generated user unit, and prove both declared services
  and the broker return healthy.
- Residual risk: recovery begins only after the operator user session starts;
  it is not pre-login availability.

## Follow-Up

- Required follow-up: None after consumer opt-in and recovery rehearsal pass.
- Optional hardening: evaluate linger only if a future requirement explicitly
  needs pre-login availability.
- Owner: `platform-engineering`.
