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
- active provider: host Ollama `0.32.14` with pinned `qwen3:8b` digest
- provider credentials: none for the local route; future paid credentials remain gateway-custodied
- audit ledger: local PVC-backed dev-integration ledger only
- direct consumer provider egress: denied by the dev-integration network-policy
  proof

The runtime proves a real bounded Ollama invocation, caller identity capture,
model and runtime integrity, strict provider output, audit emission, and
gateway-only consumer egress in dev-integration. Workspace consumption remains
separately gated by the dependent consumer activation work.

## Selected Intake Binding

`intake-classifier-v1` is a provider-neutral logical profile. Dev-integration
selects `qwen3:8b` through the local Ollama route. The OpenAI Responses API and
`gpt-5.6-terra` binding remains recorded as an inactive future paid route under
separate activation work.

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
