# Console Platform Integration Scripts

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

`proposal_target_identity.py` commissions that dedicated exact-repository
GitHub App and projects only its short-lived token, read-only Prototype Studio
authority, and persistent Proposal Target state into OOS. It never reuses
Prototype Landing, Maturity, Closure, Agent Gary, or ambient human credentials;
suspension and revocation leave source and review evidence intact.
