# Runtime Contract

## Scope

Platform projects `console-operator-identity/v1` from an active local
`dev-integration` session. The projection is a server-side read model, not an
authentication credential.

Platform projects `console-runtime-observations/v1` from the exact admitted
Kubernetes workloads in `runtime-observation-policy.yaml`. It is a short-lived
runtime read model, not proof that an endpoint or workflow succeeded.

The same policy carries the locally commissioned
`portfolio-product-runtime-health/v1` capability. It maps admitted workload
observations to exact Workspace Governance product identities and owner
recovery routes without mixing product lifecycle, publication, release, or
Security posture into runtime availability.

## Guarantees

- operator and profile must be admitted by source policy
- manifest must be an operator-owned `0600` regular file
- manifest operator must match the invoking operating-system account
- session start, expiry, source profile, and session identity are explicit
- roles and named authority come only from reviewed policy
- publication is atomic and `0600`
- repeated issue for the same session is deterministic
- a different active session cannot replace the projection without revocation
- stale, expired, malformed, unavailable, or conflicting input fails closed
- receipts contain hashes and references, never secret values
- runtime observations declare source, observation time, expiry, workload
  availability, capability posture, and recovery ownership
- missing workloads and zero ready replicas project unavailable instead of
  becoming synthetic success
- partial readiness projects degraded and collector authority failures stop
  publication
- runtime observations expire after the policy window and must be recollected
- product health binds the exact runtime projection URI and digest plus the
  exact Workspace Governance product inventory revision and digest
- product availability is one of `available`, `degraded`, `unavailable`, or
  `unknown`; stale or unobserved products are always `unknown`
- product-health receipts are versioned, bounded, and secret-free

## Limits

The local operating-system account remains inside the `dev-integration` trust
boundary. This implementation does not claim federated login, MFA, remote
revocation, stage readiness, production readiness, or Security acceptance.

Console route enforcement and OOS workflow authorization remain separate
controls. A valid projection alone grants no domain mutation authority.

Runtime workload readiness is distinct from WSL host telemetry and from the
Console's configuration capability projection. It grants no workflow,
deployment, release, recovery, or Security authority.

Product-health publication is active only in the local `dev-integration` lane
commissioned by Security `#1271` and Platform `#1273`. It remains a read-only
projection and grants no lifecycle, publication, runtime, release, access, or
Security authority.

## Cross-Domain Activation

The Platform activation command may compose only the exact reviewed Console,
OOS, and WGCF revisions declared in `cross-domain-activation-policy.yaml`.
Console access to OOS and WGCF is server-only and loopback-bound. The generated
receipt proves source revisions, owner visibility, restart, or rollback without
containing credentials or owner payloads.

Rollback removes only Console-owned user services and the dedicated WGCF
history-reader credential. It must preserve owner databases, workflow state,
evidence stores, profile sessions, and unrelated runtimes.

## Complete Runtime

The complete-runtime coordinator reuses `refinement-catalog` and adds one
authenticated cluster-local OOS-to-Platform owner route. Its catalog is a
closed action set, every command binds current source plus exact operator
approval, and caller input cannot select an executable, URL, header, secret,
or arbitrary argument.

Security accepts the exact candidate Platform tree rather than requiring the
candidate to embed its own future commit. At activation, current clean
Security `origin/main` supplies the exact decision and reviewed revision set;
Platform materializes those bindings only in mode-`0600` private state.

Worker recovery binds PID, kernel boot identity, and process start ticks.
Missing or changed identity becomes a visible retryable blocker and is never
used as a signal target. Stale activation state withholds effect capabilities.
Rollback removes only the dedicated provider, OOS binding, Console services,
and generated credentials; teardown additionally suspends the reused
composition while preserving owner evidence.

### Current canonical data under reviewed controls

The complete-runtime owner maintains private, bounded Git snapshots for the
fixed Workspace Governance and Prototype Studio providers. Only approved
record/inventory paths and Studio incubation application source may advance
from the reviewed control revision. Policy, schemas, control code, executable
modes, symlinks and rewritten history remain denied. Primary execution-source
checkouts are never pulled or reset by refresh.

Source-owner registration companions are a narrow semantic exception, not
general data paths: the exact derived owner rule, bounded routing-index region,
conservative context declarations and existing generated metadata must match
the reviewed WG projector and pass the complete owner contract model. Core or
custom policies and instructions outside the index remain unchanged. Candidate
code is never imported; code paths/modes/history are frozen before bounded
snapshots are verified using the reviewed owner's code. Missing companions,
raw-projection grants, altered instructions, extra rules or verification failure
withhold freshness. Legacy reviewed control without this projector cannot admit
these companion paths. This source extension remains uncommissioned until exact
composed Security acceptance and the normal complete-runtime activation.

The existing credential timer refreshes records every minute and atomically
publishes a five-minute owner/ref/revision checkpoint. A failed refresh
invalidates both owners while credential maintenance continues. OOS, WGCF and
the fixed Studio Preview owner adapter require that freshness proof. Runtime
status verifies consumed read-only mounts and current live Prototype and
Delivery registers, not only producer files or homepage health.

The new source-realization profile retains the existing provider, model,
gateway and caller boundaries. Platform structural validation does not
replace OOS semantic validation, explicit exact-digest acceptance or Gary's
source executor. It is commissioned only with the exact composed Security
decision and operating proof.

Normal activation and the Platform provider reuse the admitted composition
oneshot with retained supervision. A product-owned drop-in composes the full
runtime so ordinary startup cannot silently revert owner mounts or lose
detached helpers with the request controller. Uncached full operating proof
also requires retained supervision. Rollback restores prior mounts and flags,
removes that drop-in and preserves both owner data and the generic unit.

Current clean Security source is always revalidated. Acceptance provenance
uses the last commit touching the relevant decision/review files, so unrelated
generated index updates do not invalidate otherwise identical acceptance.
Changed or revoked decisions do invalidate it.
