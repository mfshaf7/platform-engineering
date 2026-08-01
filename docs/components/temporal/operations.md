# Temporal Operations

## Current Operational Posture

Temporal is build-admitted and has no running platform footprint.

The supported status check is:

```bash
make devint-status PROFILE=temporal
```

Runtime launch, diagnostic access, backup, restore, and workflow execution fail
closed while the profile is build-admitted.

## Controlled Commissioning Proof

This section is the primary Platform operator surface for a bounded Temporal
commissioning proof. The proof is not a normal profile launch and does not
change the profile from `build-admitted`.

Current availability is contract-only. No permit issuer or proof executor is
active, so operators must stop after preflight until ART #792 lands the exact
reviewed issuer and executor source, the exact permit is Security-authorized
against those revisions, and the operator explicitly approves it. The ordinary
`devint-up`, access, smoke, backup, restore, and workflow commands remain denied
and cannot substitute for this procedure.

The commissioning procedure is governed by the shared runtime-drill ledger:

- [machine-readable drill profile](../../../environments/shared/runtime-drills/temporal-component-commissioning-proof.yaml)
- [evidence-pack template](../../../environments/shared/runtime-drills/temporal-component-commissioning-proof-evidence-template.yaml)
- [runtime-drill standard](../../standards/governed-runtime-drill-model.md)
- [Security contract review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-01-temporal-controlled-commissioning-proof-contract.md)

Inspect the profile before authorization:

```bash
make platform-drill ACTION=plan PROFILE=temporal-component-commissioning-proof
```

After receiving the exact authorization artifact, create the governed ledger
and bind its durable reference and digest before any runtime mutation:

```bash
make platform-drill ACTION=snapshot \
  PROFILE=temporal-component-commissioning-proof \
  RUN_ID=<run-id> \
  OPERATOR=<operator> \
  AUTHORIZATION_REF=<durable-authorization-ref> \
  AUTHORIZATION_DIGEST=sha256:<authorization-digest> \
  NOTE="<proof purpose>"
```

The resulting `.platform-drills/temporal-component-commissioning-proof/<run-id>/`
directory is the local run ledger. It contains the baseline, verification,
exception, restore, and evidence records. Promote bounded summaries and refs to
the active ART and Security evidence surfaces; do not commit the raw local
ledger.

The snapshot starts with a pending baseline. Before activation, attest every
scoped surface against operator-reviewable evidence:

```bash
make platform-drill ACTION=attest-baseline \
  RUN=<run-dir> \
  SURFACE=<temporal-runtime|oos-validation-readiness-worker|wgcf-readiness-activity-worker> \
  ACTOR=<operator> \
  EVIDENCE_REF=<durable-pre-run-evidence-ref> \
  NOTE="<observed pre-run state>"
```

Run the command once for each scoped surface. The ledger keeps the baseline
phase pending until all three attestations have non-empty evidence refs, and
the `activate` action rejects an incomplete baseline.

### Preflight

1. Confirm `make devint-status PROFILE=temporal` reports the expected
   build-admitted, non-running baseline.
2. Run the drill `plan` command and validate one unexpired permit against the
   Workspace Governance `controlled-runtime-proof-authorization` schema.
3. Confirm ART #792 is complete and the permit binds the exact merged issuer
   and executor source revisions and their finalized Review Packet.
4. Confirm the permit binds exactly one `validation-readiness-run` version,
   every source revision, immutable runtime image and artifact digest,
   namespace, identity, task queue, scenario, and permitted action.
5. Confirm the permit carries Platform issuance, a separate Security
   authorization reference, explicit operator approval, evidence custody, and
   `exact-baseline` restore.
6. Compare every permit binding with the checked-out Platform, OOS, and WGCF
   source and the current orchestration allowlist. A schema-valid but stale or
   mismatched permit is denied.
7. Capture the exact pre-run baseline, including the expected absence or
   presence of namespaces, workloads, storage, credentials, and operator-local
   state. Do not start if the baseline cannot be proven.

### Bounded Execution

Only the reviewed issuer and executor may perform these steps:

1. Create the drill snapshot with the permit reference and digest, run
   `attest-baseline` for every scoped surface, and revalidate the permit
   immediately before the first mutation.
2. Install only the scoped runtime and start only the exact OOS and WGCF
   workers bound by the permit.
3. Run the required nominal, restart, replay, duplicate-suppression,
   cancellation, dependency-failure, identity-denial, payload-boundary,
   backup/restore, and exact-baseline-restore scenarios.
4. Execute at most one permitted `validation-readiness-run`; no business
   definition or unrelated diagnostic action is allowed.
5. Preserve correlated Platform, OOS, and WGCF receipts and the bounded logs
   required by the permit's evidence owner.
6. Remove the scoped runtime and restore the captured exact baseline before
   declaring the proof complete.
7. Verify the restored state against the pre-run evidence, then route the
   proof result to a separate post-run Security review. The pre-run permit is
   never activation evidence.

Record each baseline attestation, activation, verification result,
supplemental evidence, and restored surface through `make platform-drill
ACTION=<attest-baseline|activate|verify|record|restore> RUN=<run-dir> ...`.
Blocked checks and restore exceptions must use one of
`remove`, `workaround`, `accept-risk`, or `defer` with justification, owner,
and review date. The ledger records owner actions; it never performs an
undeclared runtime mutation itself.

### Fail-Stop Conditions

When any terminal stop condition triggers, deny every new proof action,
workflow or activity start, retry, verification mutation, scope expansion, and
activation action. This includes authorization expiry, source or artifact
drift, target-scope mismatch, identity or queue denial failure, an unavailable
baseline, unexpected side effects, evidence-custody failure, and restore
failure.

For an already-started run, continue only the fixed cleanup path: remove the
scoped runtime, restore the exact captured baseline, record restore evidence,
or record a governed exception. Cleanup stays bound to that run and captured
restore scope and ends when restoration completes or the exception is
recorded. It cannot preserve the runtime, retry proof work, widen scope, or
reopen proof authority. A restore failure enters the governed exception path.

### Required Evidence

- permit id and digest plus Platform, Security, and operator approval refs
- exact source revisions, images, artifacts, namespace, identities, and queues
- scenario outcomes, correlated run and activity receipts, and bounded logs
- pre-run baseline, backup, removal, restore, and post-restore verification
- stop-condition or exception decision when the run does not finish normally
- separate post-run Security decision before any later lifecycle change

Successful completion proves only the permitted local commissioning scope. It
does not make the profile self-serve, activate a workflow definition, or create
stage or production evidence.

## Implemented Source Boundary

- immutable chart and image pins
- operator-scoped Kubernetes and Temporal namespace rendering
- 10Gi local-path PostgreSQL persistence
- separate runtime, PostgreSQL, OOS, WGCF, and diagnostic identity references
- explicit workflow and activity task queues
- default-deny network policy and no public UI ingress
- reference-only payload and search-attribute allowlists
- read-only smoke, persistent suspend, explicit backup and restore, and
  confirmed destructive reset
- quiesced two-database backup with state-preserving completion and fail-safe
  restore behavior
- digest-pinned workflow-generation retirement manifest issuance and OOS
  receipt verification

## Activation Checks

Before the profile becomes `active`, prove:

- owner runtime commands are runnable against the controlled runtime
- PostgreSQL migration, persistence, backup, restore, and reset behavior
- runtime and OOS worker restart survival
- deterministic replay compatibility
- workflow and activity idempotency
- retry, timeout, cancellation, and suspension behavior
- namespace and task-queue identity isolation
- metrics, logs, traces, retention, and redaction
- current security acceptance

## Initial Runtime Proof

The first controlled execution is `validation-readiness-run`. Its workflow
worker polls only the queue generation derived from the currently accepted
activation-manifest digest. A revoked digest is never reused; a fresh
activation therefore cannot execute a late start retained on an older queue.

It must:

- use an OOS-owned versioned definition
- invoke only bounded WGCF readiness activity
- survive a runtime or worker restart
- preserve one correlation chain
- produce the expected orchestration receipt
- remain local dev-integration evidence

The first business workflow, `delivery.refinement.apply`, follows only after
the safe proof and definition admission pass.

## Planned Generation Retirement

Do not use activation-evidence removal as a cleanup mechanism. An unexpected
loss makes the ordinary OOS worker fail-stop with an incomplete fence; it does
not authorize polling the old queue or claim its executions are retired.

For a planned retirement:

The source-valid issuer and verifier require Python 3 and the OpenSSL CLI. The
OOS public key supplied to either command must be the exact key whose digest is
pinned in the retirement manifest.

1. quiesce OOS start ingress
2. prove start-ingress replicas and in-flight starts are both zero
3. scale ordinary OOS workflow pollers to zero and retain that evidence
4. issue the old generation's manifest with
   `generation_retirement.py issue`, including the OOS receipt key id and
   public key
5. mount the manifest read-only for the OOS `retire` one-shot command and pass
   its exact digest
6. retain the emitted receipt and run
   `generation_retirement.py verify-receipt` with the pinned public key
7. issue no fresh activation until the verifier returns `accepted`

The issuer requires explicit timestamps, evidence references, and zero counts;
it derives both the business queue and generation start registry from the
pinned activation-manifest digest, pins the OOS Ed25519 receipt verifier, and
writes a mode-0600 JSON file atomically. OOS serves both generated queues
continuously during ordinary operation. Business starts register through
Update-with-Start, with a maximum of 512 accepted registrations in one
generation. A full generation returns the stable OOS
`409 orchestration_generation_capacity_exhausted` response and must be retired
before a fresh generation is activated. OOS uses and workflow-validates one
deterministic Update ID per business workflow, so retries resolve the original
Update; rejected Updates do not enter workflow history.
Drain observations must be no more than five minutes old and the manifest
lifetime cannot exceed fifteen minutes. The verifier rejects future receipt
times, mismatched targets, digests, queues, registry identities or seals, and
incomplete reconciliation counts, forged receipt signatures, or a verifier key
whose bytes differ from the manifest pin. Every registry entry must be accounted for
as a matched execution or an uncommitted business start, and every matched
execution must have a terminal projection. It also requires the registry seal
to belong to the exact retirement authorization and the OOS one-shot start
timestamp to fall inside the manifest lifetime while allowing a valid drain to
complete after that authorization window. The acknowledged seal
Update-with-Start carries manifest issuance and expiry plus a deterministic
authorization-derived Update ID. The registry independently checks that ID and
handler time before mutation. An expired Update returns
`seal-not-authorized` and leaves the registry open for a fresh authorized
retry. A retry
after the registry was sealed requires a refreshed manifest that explicitly
resumes the exact authorization that sealed the registry and its original
lifetime. Both drained-state
observations must still be no more than five minutes old when the one-shot
worker starts.

Receipt verification is byte-exact. The manifest pins the canonicalization and
signed-content identifiers, and the verifier reproduces the compact UTF-8 bytes
from the receipt without its top-level `attestation`. The checked-in
cross-language vector must pass before the source validator accepts this
profile.

This operator surface is source-valid now. It does not make the build-admitted
profile launchable and must not be used as evidence that a retirement run has
already occurred.

## Common Failure Signals

- proposed or build-admitted profile is treated as launchable
- Console or another caller attempts direct Temporal access
- OOS and an activity owner disagree on workflow ownership
- workflow payload contains secrets, raw context, or unbounded artifacts
- worker restart loses progress or duplicates a non-idempotent effect
- task queues allow the wrong worker boundary
- profile shutdown destroys persistent history
- a fresh activation is issued without the prior generation's accepted
  retirement receipt

## First Response

1. stop new workflow starts through OOS
2. preserve workflow and platform evidence
3. classify the failure as runtime, workflow definition, activity, identity,
   persistence, or projection
4. repair the owning boundary
5. replay or retry only through the admitted OOS control

## Evidence To Capture

- exact OOS definition id and version
- Temporal and worker source or image versions
- namespace and task queue
- run, correlation, and causation references
- restart and replay outcome
- activity and final receipt references
- persistence and restore evidence
- security review reference
- start-ingress and ordinary-poller drain evidence references
- retirement manifest and receipt digests

## Related Procedures

- [README.md](README.md)
- [architecture.md](architecture.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
