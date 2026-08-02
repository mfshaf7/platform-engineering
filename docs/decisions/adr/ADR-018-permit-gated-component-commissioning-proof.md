# ADR-018: Permit-Gated Component Commissioning Proof

## Status

- Accepted

## Context

A build-admitted component can need one bounded runtime proof before normal
launch is authorized. The existing shared drill types cover product runtime,
the active stack, an environment-complete estate, and lifecycle controls. None
of them describes a narrow proof that temporarily commissions one component
and its exact participating workers while normal launch remains denied.

Treating that proof as an ordinary profile launch would bypass the runtime-
drill ledger, exact-baseline restore, exception handling, and separate Security
decisions. Treating it as an active-stack drill would overstate its scope.

## Decision

Extend the shared runtime-drill taxonomy from
[ADR-014](ADR-014-governed-active-stack-runtime-drill-and-restore.md) with
`component-commissioning-proof`.

This drill type:

- uses `runtime-drill` authority and does not change component lifecycle
- requires an exact, unexpired authorization artifact issued by Platform,
  separately authorized by Security, and explicitly accepted by the operator
- binds its component, the exact reviewed permit-issuer and executor revisions,
  source revisions, immutable artifacts, identities, queues, scenarios,
  permitted actions, evidence owner, expiry, and run limit
- rejects conflicting logical bindings, binds both approvals to an RFC 8785
  digest of every authorization field outside the approval envelope, and
  atomically consumes one authorization for one run before the first mutation
- accepts the Security approval only when the exact approval JSON is present in
  the clean, permit-bound `security-architecture` revision; a self-declared
  local Security role is not authority
- revalidates the permit, both approvals, canonical consumption receipt,
  execution claim, output root, namespaces, and collision-resistant state root
  before every internal shell mutation
- captures and binds the pre-run baseline by immutable digest before permit
  issuance and emits a schema-valid controlled-proof result artifact after
  restoration with exact keyed coverage of every authorized scenario and no
  passing outcome when restoration ends through an exception
- creates a governed local ledger before mutation
- keeps baseline capture pending until every scoped surface has an operator-
  reviewable evidence reference
- fails closed before activation when authorization or baseline evidence is
  incomplete
- records activation, verification, exceptions, and restoration through the
  shared runtime-drill model
- restores every scoped surface to the attested exact baseline
- denies new proof actions after any terminal stop condition while preserving
  only run-bound, exact-baseline cleanup authority for an already-started run
- requires a separate post-run Security decision before any later lifecycle
  change

The first profile is the Temporal controlled commissioning proof for the
Temporal runtime, the OOS validation-readiness worker, and the WGCF readiness
activity worker. It permits at most one bound `validation-readiness-run` and
does not authorize normal Temporal launch or unrelated workflow execution.

## Consequences

What becomes simpler:

- a narrow component proof has an honest taxonomy instead of borrowing a
  broader drill or a normal launch path
- authorization, baseline evidence, exceptions, restore, and receipts share
  one machine-readable control surface
- successful proof evidence cannot silently promote the component lifecycle

What becomes stricter:

- every scoped baseline surface must be attested before activation
- the permit-issuer and executor source must be reviewed before Security
  authorizes a permit, and both must validate and atomically consume one exact
  authorization artifact
- the per-run Security artifact must land in `security-architecture` before
  Platform can issue the permit, and the internal runtime adapter cannot trust
  caller-supplied environment flags as proof of authority
- the proof must stop on scope drift and restore the captured baseline
- normal profile commands remain denied until a later governed lifecycle
  decision

No change record is required for this ADR because it defines a contract and
does not activate runtime state. A later governed proof must carry its own ART,
Security, runtime-drill, and restore evidence.

## Alternatives Considered

- Use `product-runtime-drill` for component commissioning.
  - Rejected because a shared infrastructure component and bounded workers are
    not a product runtime, and the label would obscure the authorization model.
- Use `active-stack-runtime-drill` for the proof.
  - Rejected because that drill covers a broader mixed-lane stack and would
    overstate what was commissioned and verified.
- Allow one ordinary dev-integration launch while the profile is
  build-admitted.
  - Rejected because it would bypass permit scope, baseline attestation,
    exception handling, exact restore, and post-run Security review.

## Related Artifacts

- [ADR-014](ADR-014-governed-active-stack-runtime-drill-and-restore.md)
- [ADR-017](ADR-017-temporal-durable-workflow-runtime.md)
- [governed runtime-drill model](../../standards/governed-runtime-drill-model.md)
- [Temporal operations](../../components/temporal/operations.md)
- [Security contract review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-01-temporal-controlled-commissioning-proof-contract.md)
- [authorization schema](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/schemas/controlled-runtime-proof-authorization.schema.json)
- [result schema](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/schemas/controlled-runtime-proof-result.schema.json)
