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
- stop or roll back workers
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
