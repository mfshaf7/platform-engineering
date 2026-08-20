# Governed AI Gateway Dev-Integration Profile

This is the local `dev-integration` profile for the platform-owned governed AI
access-plane gateway.

The profile exists to prove the access-plane runtime before any workspace
consumer treats AI output as governed. It is not a custom LLM gateway and it
does not approve live model-profile consumption by itself.

## Runtime Boundary

When active, the profile runs:

- `governed-ai-gateway` API in a local-k3s namespace
- provider credential custody in a gateway-only Kubernetes Secret
- PVC-backed audit ledger storage
- a consumer probe namespace with default-deny egress
- a provider sentinel namespace that represents direct-provider bypass
- NetworkPolicy that allows the consumer probe to reach only DNS and the
  gateway service for AI invocation

The gateway profile status and upstream model status remain policy inputs. The
current `intake-classifier-v1` profile is still suspended until the security and
workspace activation gates are completed.

The profile reads its selected provider, route, and model directly from
`security/governed-ai-model-profiles.yaml`. The current binding is OpenAI
Responses API plus `gpt-5.6-terra`; it is exposed in status and smoke evidence
without activating the profile or calling the provider.

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

`devint-smoke` is read-only. It proves gateway readiness, caller identity
capture, audit emission, provider-secret custody, gateway reachability from the
consumer probe, and denial of the direct-provider sentinel path.

## Denied Paths

- Do not put provider credentials in workspace or consumer repos.
- Do not call external providers directly from governed consumers.
- Do not treat dev-integration evidence as governed `stage` or `prod`
  approval.
- Do not activate `intake-classifier-v1` until the profile, gateway, audit,
  egress, security, and workspace consumer gates are all proven.

## Stage Handoff Checks

The stage handoff is not ready until it proves:

- `active dev-integration profile admission`
- `gateway API readiness`
- `caller identity boundary`
- `provider credential custody`
- `audit ledger emission`
- `gateway-only consumer egress proof`
- `direct-provider sentinel denial`
- `current security delta review`

These checks must stay aligned with `stage_handoff.required_checks` in
`profile.yaml` and the workspace registry entry.
