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
`rollback`, and `cleanup`. Follow the product runbook; do not use this as an ad hoc owner
state or credential-management surface.
