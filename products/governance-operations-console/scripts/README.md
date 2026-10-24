# Console Platform Integration Scripts

`console_model_management.py` extends `console_complete_runtime.py` for the
Epic 1313 model-management boundary: pinned native runtime construction,
gateway-only account custody, bounded pod/network rendering, a distinct OOS
management projection, existing-timer lease renewal and access removal.
Normal use remains `make governance-console-complete-runtime`; the
`build-image` action is source-review validation and never deploys a workload.
The complete-runtime runbook owns the operator procedure.

`console_session_projection.py` is the product-local operator command for the
Console identity/session projection. It supports:

- `validate`: validate the source policy
- `issue`: derive and publish a projection from an active dev-integration
  session manifest
- `inspect`: validate and summarize a projection without exposing secrets
- `revoke`: replace an active projection with an explicit unavailable state

Use the top-level `make governance-console-session` target. Do not call this
script from browser code or use its projection as a bearer credential.

`console_runtime_observations.py` is the product-local operator command for the
Console runtime observation projection. It supports:

- `validate`: validate the admitted workload and recovery policy
- `project`: collect exact Kubernetes workload readiness into a private,
  expiring, secret-free projection and receipt
- `inspect`: validate and summarize an existing projection without printing
  the component payload

Use the top-level `make governance-console-runtime` target. The projection is
runtime evidence only; it is not workflow success, host telemetry, or
activation authority.

`console_cross_domain_activation.py` is the product-local activation command.
It validates pinned owner sources, installs the dedicated WGCF reader,
manages loopback tunnels and the Console service, verifies live owner-backed
activity, and records bounded receipts. Use:

```bash
make governance-console-cross-domain ACTION=<action>
```

Supported actions are `validate`, `activate`, `status`, `restart`, `rehearse`,
`catalog-rehearse`, `commission`, `rollback`, and `cleanup`. `commission` is
the evidence-profile entry point that runs the complete Repository/Catalog
sequence and restores normal availability. The
`governance-console-repository-catalog` target selects the separately pinned
Repository/Catalog commissioning policy and adds the server-only session
projection plus capability-specific operating proof. Follow the matching
product runbook; do not use this as an ad hoc owner state or credential-
management surface.

The `governance-console-proposal-target` target selects the exact Proposal
Target commissioning policy. It reuses the same managed loopback services and
server-only Console caller boundary while pinning the activated OOS revision,
Prototype Studio source authority, Security decision, and architecture packet.
The dedicated provider identity is delivered separately through
`proposal-target-identity`; it is never placed in the Console environment.
`proposal-target-commission` validates the completed OOS application, current
Studio merge and capture files, the exact denial matrix, and the ordered
restart/rollback/cleanup/redelivery receipts before issuing one value-free
commissioning receipt. `verify-proposal-target-commissioning` is the
non-mutating evidence-profile action and fails unless that exact receipt and
all current canonical readbacks remain valid.

Use `make governance-console-agent-console ACTION=validate` for the Platform
source contract and `ACTION=verify-operating` only after the exact #1248
Security gate and existing `refinement-catalog` bindings are active. The
verifier keeps caller credentials private and emits only credential-free
positive, negative, rollback, and source-revision evidence.

`product_publication_platform.py` is the Platform-owned Product Publication
commissioning command. It reuses the existing Console cross-domain services,
projects only integrity metadata into the Console, verifies the ancestry from
Security-reviewed capability source to exact activated OOS and WGCF runtime
bindings, records value-free receipts, and proves positive publication,
all four inactive target denials, fail-closed negatives, process-loss recovery,
restart, rollback, cleanup, and final restoration. Its separate
`verify-process-crash` action validates that exact recovery evidence without
claiming broader publication or access authority.

`proposal_target_identity.py` commissions that dedicated exact-repository
GitHub App and projects only its short-lived token, read-only Prototype Studio
authority, and persistent Proposal Target state into OOS. It never reuses
Prototype Landing, Maturity, Closure, Agent Gary, or ambient human credentials;
suspension and revocation leave source and review evidence intact.

`console_complete_runtime.py` is the single Platform bootstrap, health,
recovery, rollback, and teardown command for the complete local Console
composition. `platform_operation_provider.py` implements the authenticated
finite owner protocol OOS already consumes. Both remain gated by the external
Security acceptance described in the product runbook. The internal
`prototype_closure_disposition.py` reader verifies current exact graduation
and managed Preview absence for the same provider; it adds no runtime action
or independently callable operator workflow. It reuses the existing
Platform Closure evidence recorder and denies uncertain state.

The complete runtime remains gated by the external
exact-tree Security decision; generated policy and credential values stay in
operator-private state. Use the top-level
`make governance-console-complete-runtime ACTION=<action>` target and the
complete-runtime runbook rather than calling either script directly.

`console_record_authority.py` is an internal helper of that same lifecycle,
not another operator command or daemon. It maintains only two fixed private
record snapshots and expiring checkpoints while preserving reviewed control
code and primary checkouts. Its native Git tests cover allowed records,
physical post-bootstrap source snapshots and admitted-to-active continuity,
absence/dirty/provider/ref/symlink denials and preserving generated residue.
One fixed read-only WGCF parent consumes only these committed-source clones,
not the private record cache or live host app directories. Tests also cover
disallowed code/modes, provider failure, history rewrite, interrupted refresh,
expiry and different-UID read access. Set
`CONSOLE_NATIVE_RECORD_IMAGE_PROOF=1` when running
`test_console_record_authority.py` to additionally prove actual built OOS and
WGCF readers accept fresh checkpoints and deny expired ones with read-only
mounts and no network. The default unit suite skips only that image-dependent
case. The complete operating proof remains separately required.

The complete runtime reuses the existing Product Publication gates and decision,
projects only their four server metadata fields through the normal private
environment writer, and checks the real Console route mode. It does not enable
an owner, mutate a publication or copy stale environment values. Recovery and
rollback remain part of the same complete-runtime command.
