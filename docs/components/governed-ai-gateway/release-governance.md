# Governed AI Gateway Release Governance

## Current Release Posture

The gateway is approved for local `dev-integration` proof only after the
workspace registry marks profile `governed-ai-gateway` as `active`.

There is no governed `stage` or `prod` release yet.

Dev-integration selects the reviewed local Ollama `qwen3:8b` binding. The
OpenAI `gpt-5.6-terra` binding remains inactive and does not affect this
release posture.

## Dev-Integration Gate

Before using the gateway as activation evidence, prove:

- active dev-integration profile admission
- gateway API readiness
- caller identity boundary
- provider credential custody
- audit ledger emission
- gateway-only consumer egress proof
- direct-provider sentinel denial
- direct Ollama denial from the consumer namespace
- pinned Ollama version and model digest
- strict provider schema plus bounded timeout, retry, concurrency, and output
- provider route and upstream model match the approved profile registry
- both the model profile and the independent access-plane activation gate admit
  invocation
- current security delta review

## Stage Gate

Stage remains blocked until the dev-integration shape has reviewed source
changes, current security approval, release rollback controls, and a platform
stage candidate.

## Rollback

If any activation evidence fails:

- set `intake-classifier-v1` to `suspended` or close access-plane activation
- scale down the dev-integration gateway if the failure is runtime-specific
- preserve audit ledger evidence
- record the blocker or security finding before adjacent activation continues

## Non-Goals

- no direct provider passthrough
- no consumer-held provider credentials
- no production activation from dev-integration
- no model output writing workspace truth without operator acceptance
