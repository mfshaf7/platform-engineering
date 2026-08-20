# Governed AI Gateway Dev-Integration Profile

This is the local `dev-integration` profile for the platform-owned governed AI
access-plane gateway.

The profile exists to prove the access-plane runtime before any workspace
consumer treats AI output as governed. It is not a custom LLM gateway and it
does not approve live model-profile consumption by itself.

## Runtime Boundary

When active, the profile runs:

- `governed-ai-gateway` API in a local-k3s namespace
- provider-neutral binding resolution from the platform registry
- a bounded local Ollama adapter with pinned version and model digest
- PVC-backed audit ledger storage
- a consumer probe namespace with default-deny egress
- a provider sentinel namespace that represents direct-provider bypass
- NetworkPolicy that allows the consumer probe to reach only DNS and the
  gateway service for AI invocation

The gateway profile and access-plane activation states remain independent
policy inputs. The local platform route is active; workspace consumer use is
still gated by its dependent activation work.

The profile resolves the environment-selected binding from
`security/governed-ai-model-profiles.yaml`. Dev-integration calls host Ollama
with `qwen3:8b`; the future paid OpenAI binding remains inactive.

## Operator Actions

Use the shared platform runner after the workspace registry marks this profile
`active`:

```bash
make devint-up PROFILE=governed-ai-gateway
make devint-status PROFILE=governed-ai-gateway
make devint-access PROFILE=governed-ai-gateway
make devint-smoke PROFILE=governed-ai-gateway
make devint-down PROFILE=governed-ai-gateway
make devint-reset PROFILE=governed-ai-gateway
make devint-promote-check PROFILE=governed-ai-gateway
```

`devint-smoke` is read-only with respect to canonical workspace truth. It runs
a bounded model suggestion and proves caller identity, strict output, audit
emission, exact model/runtime identity, gateway reachability, and denial of
direct sentinel and Ollama paths from the consumer.

## Denied Paths

- Do not put provider credentials in workspace or consumer repos.
- Do not call external providers directly from governed consumers.
- Do not treat dev-integration evidence as governed `stage` or `prod`
  approval.
- Do not enable the workspace consumer until gateway, audit, egress, security,
  and consumer gates are all proven.

## Stage Handoff Checks

The stage handoff is not ready until it proves:

- `active dev-integration profile admission`
- `gateway API readiness`
- `caller identity boundary`
- `provider credential custody`
- `audit ledger emission`
- `gateway-only consumer egress proof`
- `direct-provider sentinel denial`
- `direct Ollama denial from governed consumer`
- `pinned Ollama version and model digest`
- `strict provider output and bounded failure handling`
- `current security delta review`

These checks must stay aligned with `stage_handoff.required_checks` in
`profile.yaml` and the workspace registry entry.
