---
security_evidence:
  review_areas: [runtime, delivery, ai]
  reviewed_artifacts:
    - security/governed-ai-model-profiles.yaml
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/test_console_complete_runtime.py
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console recovery dependency and timing repair

## Summary

Operator-authorized maintenance of the existing local complete Console lifecycle.
No new ART initiative, package-registry service, identity or browser authority.
Landing Unit Decision: feature_single_landing_unit, maintenance-console-recovery-platform-20261030, one owner review and rollback boundary.

## Classification

Corrective owner maintenance of the admitted local dev-integration lifecycle.
Runtime and delivery security delta; no new component or authority.

## Ownership

Owner: `platform-engineering`. Platform owns complete lifecycle timing and diagnostics;
OOS owns profile dependency preparation and worker readiness. Security retains
exact composed acceptance. Review: [recovery timing delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-30-console-recovery-timing.md).

## Root Cause

Automatic retry started01:33:58+08, failed its delivery participant at01:48:39,
then hit the outer15-minute deadline01:48:58 during compensation. Worker init
began01:45:39 and remained initializing at teardown, consistent with the separate
180-second rollout deadline; exact stderr was lost when the capturing parent
was terminated. A prior worker became ready27seconds before the first deadline.
Fresh init containers repeatedly downloaded packages; observed API installs took
three and six minutes, and the worker made159uncached package fetches. The whole
lifecycle inherited a generic profile timeout. Buffered output and deferred
result publication obscured the exact interrupted step. Hardware crash cause is
unverified; no source corruption is asserted.

## Source Changes

Share an operator-private npm download cache among the existing three OOS init
containers; keep fresh lockfile-based installs and package integrity, bound fetch
and install work, and drop package installation to the operator uid/gid. Reject a
symlink cache root. Increase the worker rollout allowance to600seconds while
retaining deployment-generation checks and failure propagation. Give only the
complete-runtime drop-in a finite45-minute cold-start budget. Retain composition
output privately before completion and expose fixed credential-free phase labels.
The selected API image's different lockfile is not accepted as current dependencies.

## Live Verification

Source checks and regressions cover slow cold preparation, actual rollout failure,
interrupted parent output retention, source safety and existing lifecycle behavior.
Exact committed CI-equivalent validation, hosted checks and delegated review are
required before merge. Native cold/warm recovery, current source, consumed bindings,
model/owner readiness and the pending compact VMEM UI proof remain required after
exact Security acceptance; this source record does not claim operating completion.

## Artifact And Deployment Evidence

No image or chart digest changes. Final merged owner revisions and Platform tree
require exact composed acceptance; source checks do not activate this repair.

## Rollout And Rollback

Land OOS and Platform owner changes, then exact Security acceptance and generated
change-record index. Advance only accepted clean canonical sources and use normal
complete-runtime activation. Preserve original data, durable generation, sessions,
identities and histories. Existing owner rollback remains authoritative; the
package cache is disposable data, never a substitute source or a ready marker.

## Follow-Up

Retain private native evidence, revoke exact maintenance credentials and retire
branches/worktrees after operating proof. No further capability or new work item
is proposed by this repair.

## Observed provider reconciliation after native startup

The first accepted repaired startup passed dependency preparation and served the
new Console artifact, then failed final source-realization readiness. A bounded
metadata read from the actual gateway observed Ollama0.40.13, while all six local
bindings still selected0.40.11. The qwen3:8b model digest remains
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
The timing of the host update is unverified; source corruption is not asserted.

Reconcile those six existing runtime pins only. Preserve the model, digest,
callers, limits, environments, exact version/digest checks and approved purposes.
The existing metadata readiness probe now reports its bounded failure code to
Platform instead of terminating inside kubectl and losing the reason. Python
continues to reject every non-ready or malformed response. A regression verifies
integrity denial remains denied and arbitrary diagnostic content is suppressed.
No new model mechanism or readiness exception is introduced. This follow-on
Landing Unit is maintenance-ollama-runtime-platform-20261030; it retains the same
owner review, deployment and rollback boundary and requires updated exact Security
source/tree acceptance before the existing activation command.
