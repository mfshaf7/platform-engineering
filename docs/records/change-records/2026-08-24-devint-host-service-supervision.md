# Dev-Integration Host-Service Supervision

## Summary

- Date: 2026-08-24
- Short title: declared persistent host-service lifecycle
- Environment: local dev-integration
- Severity: runtime correctness defect

## Classification

- Type: shared platform runner correction
- User-facing impact: active profiles can declare required host-side services
  that remain healthy after `up` returns and are visible through normal status
  and teardown commands.

## Ownership

- Owning repo or layer: `platform-engineering`
- Consumer repo: `operator-orchestration-service` under ART work-item #986
- Related ART defect: #985
- Related ADR:
  [ADR-020](../../decisions/adr/ADR-020-dev-integration-declared-host-services.md)
- Existing security boundary:
  [accepted-idea-delivery local profile review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-04-20-operator-orchestration-service-dev-integration-accepted-idea-delivery.md)

## Root Cause

- Immediate failure: the accepted-idea-delivery `up.sh` backgrounded a roadmap
  reconciler, then the shared runner terminated the action process group after
  successful completion.
- Actual root cause: the runner had only a temporary action lifecycle and no
  declared persistent host-service lifecycle.
- Why it escaped earlier controls: the reconciler predated later action cleanup
  hardening, and its PID file could remain after the process died, making the
  startup result appear healthier than the runtime.

## Source Changes

- Add a product-neutral host-service declaration and supervision module.
- Keep service command, readiness semantics, and source ownership in the
  profile owner repo.
- Record PID, Linux boot identity, process-start identity, all-source command
  digest, log path, and readiness in every local action manifest.
- Serialize concurrent lifecycle calls and retire verified service records
  removed from the selected profile.
- Preserve fail-closed process-group cleanup for undeclared action descendants.
- Add positive lifecycle, readiness failure, identity mismatch, source-change,
  concurrent launch, removed declaration, forced teardown, contract, and
  integrated action-manifest tests.

## Artifact And Deployment Evidence

- Application image: not applicable; this is a host-side shared runner.
- Governed stage or production deployment: not applicable.
- Source landing evidence: finalized Review Packet for ART #985 after PR merge.

## Live Verification

- Platform Landing Unit: synthetic foreground service remains alive after the
  action exits, reports ready, is reused by repeated `up`, and stops on `down`.
- OOS consumer proof: deferred to work-item #986 after this runner contract is
  merged.

## Follow-Up Actions

- Merge the platform runner Landing Unit first.
- Migrate accepted-idea-delivery through #986 and remove profile-owned
  backgrounding and PID lifecycle.
- Re-run the live accepted-idea-delivery `up`, `status`, and `down` sequence and
  retain its Review Packet evidence before #907 or #979 resumes.
