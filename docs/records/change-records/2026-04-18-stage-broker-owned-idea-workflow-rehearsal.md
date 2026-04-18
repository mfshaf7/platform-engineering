# 2026-04-18 stage broker-owned idea workflow rehearsal

## Summary

Completed the corrected stage rehearsal of the `/idea` command lane on the
broker-owned workflow design:

- `/idea help` is now served from the broker workflow descriptor and rendered by
  the Telegram adapter
- `/idea <text>` records a canonical `Idea` work package in OpenProject through
  `operator-orchestration-service`
- the broker read surface now returns the normalized stored record through both
  direct idea reads and source-based lookup

This supersedes the earlier stage proof that still treated `/idea help` as
Telegram-local behavior.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
  - `openclaw-telegram-enhanced`
- trust-boundary areas:
  - delivery
  - runtime
  - AI

## Ownership

- stage runtime and rollout evidence owner: `platform-engineering`
- broker source and API owner: `operator-orchestration-service`
- Telegram command adapter owner: `openclaw-telegram-enhanced`
- AI/workflow governance owner: `security-architecture`

## Root Cause

The first stage `/idea` rehearsal closed the write path but still left workflow
guidance owned by the Telegram layer. That was the wrong boundary:

- workflow semantics and operator guidance belong to the broker
- Telegram should only render the broker-owned workflow descriptor
- record visibility also needed a broker-owned projection surface instead of
  forcing operators to infer state from raw logs or OpenProject UI alone

The corrected source work landed first in the broker, Telegram adapter, and
security review layers. This record captures the governed stage proof after
those changes were rebuilt and rolled out.

## Source Changes

- no new platform-owned source behavior in this record
- this record captures governed stage evidence after:
  - the shared broker workflow-catalog and read-projection rollout
  - the stage Telegram overlay rollout that removed local `/idea help`
    ownership and consumed the broker descriptor instead

## Artifact And Deployment Evidence

- stage platform revision:
  - `95cdf661ec2b60c6856744ade6ede2b6f9589e5d`
- stage gateway app revision:
  - `95cdf661ec2b60c6856744ade6ede2b6f9589e5d`
- shared broker app revision:
  - `95cdf661ec2b60c6856744ade6ede2b6f9589e5d`
- shared broker source SHA:
  - `e09a8e0506df8ade8b3bd67ec14f57f288683562`
- shared broker image digest:
  - `sha256:671aeef58be1cd13fb5b90e85a6def35798d302ca5be228a6ff070aa645e0b2d`
- stage Telegram overlay source SHA:
  - `f2b7edb2bab1a65e4c38b25c6daaca6c93b7cc1c`
- stage Telegram overlay image digest:
  - `sha256:4301e34d8c8046e2b1d9fb2f20e47143a6a56c8b13cc8e3480d8f7c71c862710`
- Telegram overlay build workflow:
  - GitHub Actions run `24603255016`
- live stage gateway image:
  - `ghcr.io/mfshaf7/openclaw-gateway@sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`

## Live Verification

- shared broker runtime:
  - Argo child app `operator-orchestration-service` reached `Synced Healthy` on
    revision `95cdf661ec2b60c6856744ade6ede2b6f9589e5d`
  - live broker pod:
    - `operator-orchestration-service-5f5659b977-h4k5x`
  - broker `/healthz` returned `200`
  - broker `/readyz` returned `200`
  - broker `/version` returned `200`
- stage gateway runtime:
  - Argo child app `openclaw-gateway-stage` reached `Synced Healthy` on
    revision `95cdf661ec2b60c6856744ade6ede2b6f9589e5d`
  - live gateway pod:
    - `openclaw-gateway-59bffb76f7-mdx6m`
  - live overlay image:
    - `ghcr.io/mfshaf7/openclaw-telegram-overlay@sha256:4301e34d8c8046e2b1d9fb2f20e47143a6a56c8b13cc8e3480d8f7c71c862710`
- broker-owned workflow descriptor proof:
  - direct stage-gateway request to:
    - `GET /v1/workflows/idea-capture`
  - broker log correlation id:
    - `27464494-48f1-4913-a9dd-b4eb679d7fe3`
  - descriptor fields confirmed:
    - `workflow_id=idea-capture`
    - `supports.capture=true`
    - `supports.read_projection=true`
    - `supports.source_lookup=true`
    - `supports.triage=false`
    - `supports.decision=false`
    - Telegram source hint:
      - `help_invocation=/idea help`
      - invocation examples include `/idea <idea text>`
  - stage Telegram help reply sent:
    - `sendMessage ok chat=-1002519919856 message=988`
- fresh real stage `/idea` capture proof:
  - Telegram source reference:
    - `conversation_id=-1002519919856`
    - `conversation_type=supergroup`
    - `thread_id=980`
    - `message_id=989`
    - `command=idea`
  - broker log correlation id:
    - `54997f3e-5b2d-4b64-9556-bf651fd2db8f`
  - operator identity recorded by the broker:
    - `id=1338752889`
    - `handle=mfxo7`
  - OpenProject record created:
    - `openproject://work_packages/41`
  - broker status:
    - `captured`
  - stage Telegram confirmation sent:
    - `sendMessage ok chat=-1002519919856 message=990`
- broker read-projection proof:
  - direct stage-gateway request to:
    - `GET /v1/ideas/idea-41`
  - source-based request to:
    - `POST /v1/ideas/lookup`
  - broker lookup correlation id:
    - `89a85175-f2c9-46e4-a484-657604ba564f`
  - both reads returned the normalized broker-owned record with:
    - `idea_id=idea-41`
    - `workflow_id=idea-capture`
    - `record_ref=openproject://work_packages/41`
    - `record_system=openproject`
    - `status=captured`
    - title and body:
      - `our observability stack are in a very bad shape. We need to take a look at this later`
    - Telegram source identity:
      - `surface=telegram`
      - `integration_id=default`
      - `conversation_id=-1002519919856`
      - `thread_id=980`
      - `message_id=989`

## Follow-Up

- `/idea triage` and decision endpoints remain intentionally deferred
- Telegram should keep consuming broker-owned workflow descriptors rather than
  reintroducing local workflow guidance
- future non-Telegram intake surfaces should bind to the same broker catalog and
  normalized source model instead of inventing their own semantics
