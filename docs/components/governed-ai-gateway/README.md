# Governed AI Gateway

## Purpose

`governed-ai-gateway` is the platform-owned access-plane boundary for bounded
governed AI consumers.

It gives consumers one approved invocation path for governed AI use while
keeping provider credentials, caller identity checks, audit emission, and
provider-egress controls outside consumer repos.

The gateway is not:

- a custom model provider
- a general LLM gateway
- a workspace decision authority
- a replacement for security review or operator approval

## Start Here

- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)

## Current Live Footprint

- approved runtime: local-k3s `dev-integration` only
- dev-integration profile: `governed-ai-gateway`
- dev-integration namespace: `devint-governed-ai-gateway-<operator>`
- Argo application: none
- stage/prod deployment: none
- provider credentials: gateway namespace Secret only
- audit ledger: local PVC-backed dev-integration ledger only
- direct consumer provider egress: denied by the dev-integration network-policy
  proof

The current runtime proves gateway readiness, caller identity capture, provider
custody, audit emission, and gateway-only consumer egress in dev-integration.
It does not activate `intake-classifier-v1` for live workspace consumption.

## Selected Intake Binding

`intake-classifier-v1` is bound to `gpt-5.6-terra` through the OpenAI
Responses API route owned by `governed-ai-gateway`. The model profile remains
`suspended`; selection is not activation, and the dev-integration runtime still
uses the provider sentinel until the focused security review and provider-route
proof are complete.

## Owner Boundaries

- `platform-engineering` owns the gateway runtime profile, platform-side
  contracts, provider custody, and release gates.
- `workspace-governance` owns the intake-assist consumer contract and workspace
  truth updates after operator acceptance.
- `security-architecture` owns security review, findings, and activation
  acceptance.

## Security References

- [governed AI access model](../../standards/governed-ai-access-model.md)
- [AI security standard](https://github.com/mfshaf7/security-architecture/blob/main/docs/standards/ai-security-and-governance.md)
- [bounded runtime assist activation review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/platform/2026-04-29-bounded-governed-ai-runtime-assist-activation.md)
