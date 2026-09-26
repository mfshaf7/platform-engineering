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
