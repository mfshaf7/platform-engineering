# Temporal Release Governance

## Current Release State

Temporal is a build-admitted shared platform component.

There is currently no approved:

- dev-integration activation
- PostgreSQL deployment
- active operator access
- Argo application
- `stage` or `prod` deployment

The runtime source, artifact pins, and operator commands are implemented. They
do not change live state.

## Build-Admission Gate

The completed build-admission prerequisites are:

- the workspace profile becomes `build-admitted`
- Platform records persistent-runtime acceptance
- Security records the required boundary review
- implementation scope explicitly denies self-serve launch

Build admission remains bounded to source implementation and validation.

## Dev-Integration Activation Gate

Self-serve local launch requires:

- profile lifecycle `active`
- implemented owner commands
- read-only shared smoke
- accepted namespace, storage, suspend, reset, and access contracts
- OOS adapter and worker boundary
- current security acceptance

When a prior activation generation exists, fresh activation also requires:

- zero active start-ingress replicas and zero in-flight starts
- zero ordinary OOS workflow pollers
- a Platform-issued manifest pinned to the prior activation digest, both OOS
  queues, and the OOS receipt verifier key
- an Ed25519-attested OOS retirement receipt accepted by the Platform verifier
- a new activation-manifest digest that derives a different queue

An initial activation has no prior-generation receipt. Unexpected activation
loss is an incomplete fence and cannot satisfy this gate.

Local execution is not governed rollout evidence.

## Required Gates Before Stage

- reviewed and pinned Temporal artifact
- OOS adapter and admitted definition versions
- identity and task-queue authorization
- persistence migration, backup, restore, and rollback
- restart and deterministic replay evidence
- idempotency, retry, timeout, cancellation, and compensation tests
- observability, retention, and redaction controls
- security acceptance
- successful `validation-readiness-run` proof
- proof that activation-manifest digest rotation moves OOS polling to a new
  workflow queue while a same-manifest restart retains the active queue
- proof that the old queue was retired through the ordered Platform/OOS
  manifest and receipt handoff before that rotation

## Required Gates Before Production

- exact stage candidate and verification evidence
- explicit stage readiness approval
- production environment contract
- supported upgrade and rollback path
- backup and restore evidence
- support-readiness and incident procedures
- post-promotion verification

## Rollback Boundary

Contract-only changes are reverted through their source PR.

Future runtime rollback must distinguish:

- suspend new OOS workflow starts
- drain start ingress and stop both ordinary OOS queue pollers
- run an authorized one-shot retirement worker for the old generation
- retain and cryptographically verify the retirement receipt before any fresh
  activation
- roll back the Temporal artifact
- preserve or restore compatible workflow history
- suspend the profile or environment
- never discard persistent state as an implicit rollback

## Release Authority

- `platform-engineering` owns runtime release and environment state.
- `operator-orchestration-service` owns workflow implementation readiness.
- `workspace-governance` owns authority and profile lifecycle contracts.
- `security-architecture` owns security acceptance.

No workflow receipt or ART completion note substitutes for platform release
approval.
