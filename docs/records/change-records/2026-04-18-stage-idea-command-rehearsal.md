# 2026-04-18 stage idea command rehearsal

## Historical Note

This record captures the earlier stage rehearsal that still used Telegram-local
`/idea help` guidance. The current supported design is recorded in
`2026-04-18-stage-broker-owned-idea-workflow-rehearsal.md`, which supersedes
the local-help ownership model.

## Summary

Completed the real stage rehearsal of the Telegram `/idea` command lane across
two governed steps:

- initial stage `/idea` capture proof through the broker-backed path
- follow-up Telegram overlay rollout that added in-band `/idea help` guidance
  and a fresh post-rollout `/idea` capture proof

The live stage path now proves:

- `/idea help` replies locally from the Telegram layer
- `/idea <text>` records a canonical `Idea` work package in OpenProject through
  `operator-orchestration-service`

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
  - `openclaw-telegram-enhanced`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- stage runtime and rollout evidence owner: `platform-engineering`
- broker source and API owner: `operator-orchestration-service`
- Telegram command owner: `openclaw-telegram-enhanced`

## Root Cause

The new idea-command lane was not complete until stage proved both halves of
the operator experience:

- real end-to-end capture from Telegram into OpenProject
- in-band command guidance from the Telegram surface itself

The first stage rehearsal proved the capture path but exposed a usability gap:
`/idea` still needed an operator-visible help surface. The follow-up overlay
rollout carried that fix through the governed Telegram lane and re-proved the
stage runtime.

## Source Changes

- no new platform-owned source behavior in this record
- this record captures governed stage evidence after:
  - the initial broker-backed `/idea` rollout
  - the Telegram `/idea help` guidance fix delivered through the stage overlay
    lane

## Artifact And Deployment Evidence

- initial stage platform revision:
  - `3da0c240c8aaec53e759ae12bf79d46925fd9510`
- guidance rollout platform revision:
  - `baf2b7b7fef5e6870a64edb514c6aaa5b8de7ac7`
- shared broker source SHA:
  - `74c6ec8ee8570d8ca9af18078796a0bb18f022e0`
- shared broker image digest:
  - `sha256:0b93a00811f0286339f6873297cacbc4bb6f91e046852bf99df8c4bf42d40723`
- initial stage gateway app revision:
  - `3da0c240c8aaec53e759ae12bf79d46925fd9510`
- initial stage overlay source SHA:
  - `2038e4daa504a8547e7c09f498bc6f38eac23339`
- guidance rollout stage overlay source SHA:
  - `c0b004c1e60f5e7cb3a58d7e0b0f68d3bf4c258c`
- guidance rollout stage overlay image digest:
  - `sha256:a2a822f88dca521a1b648900523ce84372ba51af8e683700079eefde51edba56`
- overlay build workflow:
  - GitHub Actions run `24602127542`

## Live Verification

- shared broker runtime:
  - Argo child app `operator-orchestration-service` reached `Synced Healthy`
  - broker `/healthz` returned `200`
  - broker `/readyz` returned `200`
  - broker `/version` returned `200`
- direct broker capture proof:
  - work package `38` created in `workspace-proposals`
- initial real stage Telegram capture proof:
  - broker log correlation id:
    - `703f7268-4463-4d2e-95ee-4ab41409cf22`
  - Telegram source reference:
    - `chatId=-1002519919856`
    - `messageThreadId=980`
    - `messageId=981`
  - OpenProject record created:
    - `openproject://work_packages/39`
  - work package title:
    - `Need to consider to move to serious ingress controller for k3s`
  - stage Telegram confirmation sent:
    - `sendMessage ok chat=-1002519919856 message=982`
- guidance overlay rollout reconciliation proof:
  - Argo child app `openclaw-gateway-stage` reached `Synced Healthy` on
    revision `baf2b7b7fef5e6870a64edb514c6aaa5b8de7ac7`
  - live gateway pod:
    - `openclaw-gateway-55985f48bc-cvftx`
  - live overlay image:
    - `ghcr.io/mfshaf7/openclaw-telegram-overlay@sha256:a2a822f88dca521a1b648900523ce84372ba51af8e683700079eefde51edba56`
  - live overlay source SHA:
    - `c0b004c1e60f5e7cb3a58d7e0b0f68d3bf4c258c`
- real stage `/idea help` proof after the guidance rollout:
  - stage Telegram help reply sent:
    - `sendMessage ok chat=-1002519919856 message=984`
  - broker logs in the same stage window show no help-side write request before
    the later capture event, which confirms help stayed local to the Telegram
    layer
- fresh real stage `/idea` capture proof after the guidance rollout:
  - broker log correlation id:
    - `4b6ea21e-64f3-43c7-9848-1ae5069bf461`
  - Telegram source reference:
    - `chatId=-1002519919856`
    - `messageThreadId=980`
    - `messageId=985`
  - OpenProject record created:
    - `openproject://work_packages/40`
  - work package title:
    - `the broker api structure is still too weak. We need to look into it`
  - stage Telegram confirmation sent:
    - `sendMessage ok chat=-1002519919856 message=986`
  - canonical work package details:
    - type: `Idea`
    - project: `workspace-proposals`
    - status: `captured`
    - source surface custom field: `telegram`
    - source reference custom field:
      - `{"accountId":"default","chatId":-1002519919856,"chatType":"supergroup","command":"idea","messageId":985,"messageThreadId":980}`

## Follow-Up

- continue with `/idea triage` and decision endpoints later; they are still
  intentionally deferred
- broader stage verification for promotion readiness remains separate; this
  record only closes the `/idea` command lane proof on stage
