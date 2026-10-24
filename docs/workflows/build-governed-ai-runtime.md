# Build Governed AI Runtime

## Purpose

Publish the existing governed AI gateway's fixed executable/base artifact using
the Platform GitHub Actions/GHCR path. The local Console composition can then
pull an immutable image through Kubernetes without host image-import privileges.

## Trigger

- push to `main` changing this workflow, the Console model-image helper or its
  composition policy
- manual `workflow_dispatch` on `main`

## Inputs Or Parameters

None. The fixed version, executable digest and Python base digest come from
`products/governance-operations-console/complete-runtime-policy.yaml` and must
pass the owner helper's closed validation. The image tag derives from those
artifact inputs, independently of unrelated Platform records.

## Permissions And Approval Surface

- default `contents: read`
- only the main-only publication job receives `packages: write`
- no provider account, host-control credential or cross-repository token
- source review precedes main publication; publication does not accept Security
  scope, activate a runtime or approve provider entitlement

## Outputs And Side Effects

- downloads only the fixed public Codex release member and verifies its raw
  SHA256 before construction
- builds the accepted Python base plus one executable layer, runs its actual
  checksum check and publishes `ghcr.io/mfshaf7/governed-ai-runtime:inputs-<digest>`
- records the actual immutable registry reference in the workflow summary
- creates no workload, account lease, provider login or project content

## Guardrails

- no workflow inputs can select a repository, provider, binary URL or base
- publication job refuses branch execution outside `main`
- Docker receives only the verified public executable and generated Dockerfile
- initial package visibility must permit anonymous pulls before commissioning
- activation independently checks anonymous readability, input/source labels,
  exact base layers, executable digest and immutable registry identity before
  creating new account credentials

## Operator Evidence

- reviewed Platform commit and workflow run URL
- actual published image tag and immutable digest
- accepted executable and base digests
- separate exact-source Security decision and complete-runtime activation
- real Console/provider qualification; a successful build is artifact evidence

## Related Docs

- [Operate the complete Console runtime](../../products/governance-operations-console/runbooks/operate-complete-runtime.md)
- [Governed model management](../components/governed-ai-gateway/model-management.md)

## Follow-up

After the exact composed Security decision accepts the current source, follow
the existing complete-runtime activation procedure. Initial public-package
visibility and dedicated provider sign-in remain distinct setup requirements.
