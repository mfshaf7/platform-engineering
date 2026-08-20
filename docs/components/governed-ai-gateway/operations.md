# Governed AI Gateway Operations

## Primary Checks

Use the shared dev-integration runner:

```bash
make devint-status PROFILE=governed-ai-gateway
make devint-smoke PROFILE=governed-ai-gateway
```

Smoke is read-only. It proves:

- gateway API readiness
- caller identity reaches the access plane
- audit ledger event emission
- active binding, Ollama version, and model digest match the registry
- provider output passes the strict classification schema
- consumer can reach the gateway service
- consumer cannot reach the direct-provider sentinel service
- consumer cannot reach host Ollama directly

## Common Failure Signals

- profile is not `active` in the workspace registry
- gateway Deployment is not ready
- consumer probe cannot reach the gateway
- latest audit event is missing caller identity
- Ollama version or model digest differs from the approved binding
- provider response contains malformed JSON, extra fields, thinking, or tools
- provider request times out or the concurrency bound is exhausted
- direct-provider sentinel is reachable from the consumer probe

## First Response

1. Run `make devint-status PROFILE=governed-ai-gateway`.
2. If the profile is not active, fix workspace registry admission before
   launching runtime.
3. If runtime is active but smoke fails, inspect the generated manifest under
   `.dev-integration/governed-ai-gateway/<operator>/rendered/`.
4. If the sentinel or Ollama is directly reachable, treat the egress policy as broken
   and do not activate any governed consumer.

## Recovery Sequence

Use suspend/resume first:

```bash
make devint-down PROFILE=governed-ai-gateway
make devint-up PROFILE=governed-ai-gateway
```

Use reset only when intentionally destroying local dev-integration state:

```bash
make devint-reset PROFILE=governed-ai-gateway
make devint-up PROFILE=governed-ai-gateway
```

## Evidence To Capture

- `profile-status.txt`
- `smoke-summary.json`
- rendered runtime manifest path
- audit event digest from `/v1/audit/events/latest`
- profile lifecycle state from workspace registry

## Related Procedures

- [access.md](access.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
