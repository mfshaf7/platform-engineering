# Governed AI Gateway Access

## Dev-Integration Access

After the workspace registry marks the `governed-ai-gateway` profile `active`,
operators can use the shared platform runner from the `platform-engineering`
repo:

```bash
make devint-up PROFILE=governed-ai-gateway
make devint-status PROFILE=governed-ai-gateway
make devint-access PROFILE=governed-ai-gateway
make devint-smoke PROFILE=governed-ai-gateway
make devint-down PROFILE=governed-ai-gateway
make devint-reset PROFILE=governed-ai-gateway
make devint-promote-check PROFILE=governed-ai-gateway
```

`devint-access` opens a local port-forward to:

```text
http://localhost:18290
```

Useful read-only endpoints:

- `/healthz`
- `/readyz`
- `/v1/provider/custody`
- `/v1/audit/events/latest`

The invocation endpoint is:

- `POST /v1/governed-ai/invoke`

Requests name a logical profile and platform-owned output schema. Typed
consumers also provide the exact task kind, contract reference, and contract
version. They do not name Ollama, OpenAI, or a concrete model. The gateway
resolves the selected environment binding and returns a pre-acceptance
suggestion; the consumer records operator acceptance separately before
canonical truth can change.

`intake-classifier-v1` retains its default `intake_classification` task for
request compatibility. `delivery-work-design-advisor-v1` requires either
`context_advice` or `tree_advice` under `oos.delivery-work-design.v1`. That
profile is active only in local `dev-integration`; mismatched caller, profile,
task, contract version, input packet, or output schema is denied before provider
access.

The current profile status is intentionally policy-controlled. If the requested
model profile is not active, invocation returns a deny decision and still emits
an audit event.

## Denied Access

- no direct provider access from consumers
- no provider secret projection into consumer namespaces
- no direct host Ollama access from consumer namespaces
- no stage or prod endpoint
- no dashboard endpoint
- no raw provider token readback endpoint
- no untyped Work Design invocation
