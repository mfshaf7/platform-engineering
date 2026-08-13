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

The permit issuer and executor source is reviewed under ART #825. One permit
was issued and consumed for the first commissioning attempt. That session
stopped before scenario execution when the WGCF owner-context source binding
and sealed cleanup state-root projection failed closed. ART #832 and #833 own
those Platform corrections. The consumed permit cannot be reused; another
attempt requires a fresh baseline, claims set, Security authorization, operator
approval, and permit after the corrections land. Ordinary `devint-up`, access,
smoke, backup, restore, and workflow commands remain denied while the profile
is `build-admitted`.

The commissioning procedure is governed by the shared runtime-drill ledger:

- [machine-readable drill profile](../../../environments/shared/runtime-drills/temporal-component-commissioning-proof.yaml)
- [evidence-pack template](../../../environments/shared/runtime-drills/temporal-component-commissioning-proof-evidence-template.yaml)
- [runtime-drill standard](../../standards/governed-runtime-drill-model.md)
- [Security contract review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-01-temporal-controlled-commissioning-proof-contract.md)
- [result artifact schema](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/schemas/controlled-runtime-proof-result.schema.json)

Inspect the profile before authorization:

```bash
make platform-drill ACTION=plan PROFILE=temporal-component-commissioning-proof
```

It must report `availability=source-reviewed` and `snapshot_allowed=true`.
Those values mean only that the permit-validating snapshot path exists. The
snapshot still fails before creating a run directory unless every required
artifact is present, current, internally consistent, and unexpired.

### 1. Capture The Immutable Baseline

Capture this before assembling the claims or requesting either approval:

```bash
python3 dev-integration/profiles/temporal/scripts/controlled_proof.py \
  capture-baseline \
  --workspace-root <workspace-root> \
  --baseline-id artifact://controlled-proof/baselines/<session-id> \
  --operator <operator> \
  --output <local-evidence-root>/baseline.json \
  --evidence-root <local-evidence-root>/baseline-evidence
```

Capture refuses dirty owner repos, a running operator-scoped Temporal footprint,
operator-local Temporal state, or an installed operator-scoped OOS or WGCF
controlled worker. The resulting baseline and three runtime-surface evidence
files are immutable permit inputs. Execution source revisions remain
authorization inputs; Security approval provenance is bound later in the
approval envelope. Neither is a runtime surface that terminal cleanup later
attempts to restore.
Do not edit or recapture the baseline under the same identity.

### 2. Assemble And Approve One Claims Set

The claims JSON excludes the `approvals` envelope. It must bind the exact
merged Platform #825 revision and finalized Review Packet, the exact reviewed
Workspace Governance, OOS, and WGCF revisions in the controlled-proof source
manifest, immutable image and artifact digests, one namespace, the three
runtime identities, two task queues, eleven ordered scenarios, one baseline,
and one expiry window. Security is deliberately excluded because its approval
does not exist yet. Validate and reproduce the claims RFC 8785-subset digest.
Choose a declared issue time after both approvals can be recorded and an expiry
that bounds the whole proof, then build the claims from the immutable baseline
and reviewed source:

```bash
python3 dev-integration/profiles/temporal/scripts/controlled_proof.py \
  build-claims \
  --workspace-root <workspace-root> \
  --authorization-id platform-controlled-proof://authorizations/<session-id> \
  --session-id <session-id> \
  --review-packet-ref artifact://review-packets/<platform-825-packet> \
  --issued-at <rfc3339-utc> \
  --expires-at <rfc3339-utc> \
  --baseline <local-evidence-root>/baseline.json \
  --baseline-evidence-root <local-evidence-root>/baseline-evidence \
  --oos-api-image-digest sha256:<digest> \
  --oos-worker-image-digest sha256:<digest> \
  --wgcf-worker-image-digest sha256:<digest> \
  --output <local-evidence-root>/claims.json
```

The builder refuses dirty source, unreviewed contract-source revisions,
incomplete baseline evidence, or any non-digest owner-image binding. Reproduce
the digest independently before approval:

```bash
python3 dev-integration/profiles/temporal/scripts/controlled_proof.py \
  validate-claims --claims <local-evidence-root>/claims.json
```

Security authorization under ART #790 and explicit operator approval must each
be separate JSON artifacts binding that exact digest. The Security artifact
must also be committed and merged in `security-architecture`, identify its own
normalized JSON source path, and remain equivalent to that source-controlled
record. Before issuance, fetch `origin/main` in that repository and use a clean
checkout whose revision is contained by `refs/remotes/origin/main`. Permit
issuance fails closed if that merged ref is absent, stale, or does not contain
the Security revision. It records the exact revision, normalized source path,
artifact reference, and digest in the approval envelope without changing the
canonical claims digest. The Security artifact therefore does not embed its own
containing commit. A self-declared local role or the contract review is not a
per-run Security authorization.

### 3. Issue The Final Permit

Only after both approvals exist:

```bash
python3 dev-integration/profiles/temporal/scripts/controlled_proof.py \
  issue-permit \
  --workspace-root <workspace-root> \
  --claims <local-evidence-root>/claims.json \
  --operator-approval <local-evidence-root>/operator-approval.json \
  --security-authorization <workspace-root>/security-architecture/<security-authorization-source-path> \
  --baseline <local-evidence-root>/baseline.json \
  --baseline-evidence-root <local-evidence-root>/baseline-evidence \
  --output <local-evidence-root>/authorization.json
```

Issuance revalidates both approval files, including the Security artifact
against the clean permit-bound `security-architecture` Git revision and its
containment in `refs/remotes/origin/main`, plus the baseline files, every
current source checkout, the pinned contract-source revisions, Platform
artifacts, Temporal image locks, declared owner-image digests, identities,
queues, namespace, scenario order, implementation and Review Packet bindings,
and the validity window. ART #790 must separately verify that the referenced
Review Packet is finalized and that each approved owner-image digest has the
required source provenance. Issuance refuses to overwrite an existing permit.

### 4. Consume The Permit And Create The Ledger

```bash
make platform-drill ACTION=snapshot \
  PROFILE=temporal-component-commissioning-proof \
  RUN_ID=<commissioning-session-id> \
  OPERATOR=<operator> \
  AUTHORIZATION_REF=<authorization-id> \
  AUTHORIZATION_DIGEST=sha256:<authorization-file-digest> \
  AUTHORIZATION_FILE=<local-evidence-root>/authorization.json \
  OPERATOR_APPROVAL_FILE=<local-evidence-root>/operator-approval.json \
  SECURITY_AUTHORIZATION_FILE=<workspace-root>/security-architecture/<security-authorization-source-path> \
  BASELINE_FILE=<local-evidence-root>/baseline.json \
  BASELINE_EVIDENCE_ROOT=<local-evidence-root>/baseline-evidence \
  NOTE="<proof purpose>"
```

This is the atomic single-use point. A per-authorization local lock serializes
snapshot creation. The command writes one exclusive consumption receipt before
any runtime mutation, imports the already-attested baseline into
`.platform-drills/temporal-component-commissioning-proof/<commissioning-session-id>/`,
and writes `run.yaml` last as the snapshot commit marker.
The run id must equal the permit's commissioning session id; omitting `RUN_ID`
selects that id automatically. A custom drill-state root is denied. If the
process stops after receipt creation but before `run.yaml` is committed, the
same command may reuse only that exact matching receipt and rebuild the partial
directory, provided no execution claim exists. A committed run or claimed
execution remains single-use and is denied. Do not use generic
`attest-baseline`, `activate`, `verify`, or `record` actions for this controlled
proof. Generic successful restore attestations are denied as well.

### 5. Execute The Bound Session

Use the artifact paths and receipt digest recorded under `controlledProof` in
the run's `run.yaml`:

```bash
python3 dev-integration/profiles/temporal/scripts/controlled_proof.py execute \
  --workspace-root <workspace-root> \
  --authorization <authorization-path> \
  --authorization-digest sha256:<authorization-file-digest> \
  --operator-approval <operator-approval-path> \
  --security-authorization <security-authorization-path> \
  --baseline <baseline-path> \
  --baseline-evidence-root <baseline-evidence-root> \
  --consumption-receipt <consumption-receipt-path> \
  --consumption-receipt-digest sha256:<consumption-receipt-digest> \
  --output-root .platform-drills/temporal-component-commissioning-proof/<commissioning-session-id>/controlled-proof-output
```

The output path must be the canonical directory recorded in the Platform run
ledger; an alternate path is denied. Before every internal shell mutation, the
executor revalidates the permit and source-controlled approvals, the canonical
single-use consumption receipt, execution claim, output root, collision-
resistant operator state root, Kubernetes namespace, and Temporal namespace.
Before the persistent authorization execution claim is created, the executor
atomically acquires the canonical lease for that operator scope. Another
authorization for the same scope is denied before it can prepare or clean up a
runtime. The lease is released only after successful scoped baseline
verification.
The execute command holds one filesystem lock for the exact authorization.
It projects or revalidates the immutable owner contexts before acquiring the
claim and may resume only an identical existing claim with the same canonical
output root and still-active scope lease. A partial owner-context write is
therefore recoverable before runtime mutation without opening concurrent
execution.
Setting environment flags or plausible identifiers cannot bypass that gate.
Before its first mutation the executor creates a detached, clean checkout of
the permit-bound Platform revision. Before each runtime shell action, including
terminal cleanup after current-checkout drift, every tracked byte in the
complete Temporal profile is compared with the permit-bound commit tree and
any additional file is denied; mutable Git index flags are not accepted as
integrity evidence. The verified files are copied into sealed memory and
projected by Bubblewrap at the exact profile path as a private read-only tree.
The runtime therefore cannot execute source swapped into the checkout after
attestation. The commissioning host must provide `bwrap` in the controlled
executable path and permit its unprivileged user-namespace sandbox. The
executor probes that capability before creating the source snapshot. It
installs only the permit-bound local runtime, projects immutable
OOS and WGCF contexts, and runs the eleven scenarios in fixed order. It reserves
the final 120 seconds of the authorization window for starting exact-baseline
restore; normal proof commands are denied once that reserve is reached. A
scenario failure stops new proof work; terminal restore and cleanup still
validate the immutable permit, approvals, canonical consumption receipt,
execution claim, exact scope, and historical Security artifact at the permit-
bound revision before removing the scoped runtime. Current checkout drift or
permit expiry cannot authorize new proof work and cannot prevent that bounded
removal. Terminal verification checks the captured operator-scoped namespace,
deployments, and local runtime state; it does not require current source
checkouts to equal the pre-proof revisions. If exact restoration or its
terminal verification fails, the executor
emits an immutable stopped-result draft and no final result.

If automated cleanup stops before exact restoration, retry only the consumed
session's original cleanup scope. This command revalidates the immutable permit,
approvals, consumption receipt, execution claim, scope lease, executor snapshot,
and baseline. It cannot resume proof scenarios or authorize new work:

```bash
make platform-drill ACTION=controlled-cleanup RUN=<run-dir>
```

Record one governed exception against the run's exact captured restore scope,
including the original automated-cleanup failure even when the bounded retry
restored the baseline.
The controlled action requires the executor-created draft and cannot claim a
successful restore, select a smaller surface, or resume proof work:

```bash
make platform-drill ACTION=controlled-exception RUN=<run-dir> \
  ACTOR=<operator> \
  DECISION=<remove|workaround|accept-risk|defer> \
  JUSTIFICATION="<reason>" OWNER=<owner> REVIEW_ON=<yyyy-mm-dd>
```

Then finalize the immutable stopped result. Finalization revalidates the
authorization, consumption receipt, one-time execution claim, stopped draft,
exception digest, session, output root, scenario set, receipts, and baseline
binding. It may finish after permit expiry because it creates evidence only;
it cannot start or retry proof work:

```bash
make platform-drill ACTION=controlled-finalize RUN=<run-dir>
```

The result contains exact keyed outcomes and Platform, OOS, and WGCF owner
receipts. Route that bounded artifact to post-run Security review under #791.
Even a passing result proves only this one local commissioning scope; it does
not activate the profile, admit a general workflow, or create stage or
production evidence.

### Fail-Stop Boundary

Authorization expiry, source or artifact drift, target mismatch, failed
identity or queue denial, unavailable baseline, unexpected side effects,
evidence-custody failure, and restore failure deny new proof actions. For an
already-started session, only runtime removal, exact-baseline restoration,
restore evidence, or a governed exception remains allowed. Raw local ledgers,
credentials, command output, and unbounded logs are not promoted as evidence.

## Implemented Source Boundary

- immutable chart and image pins
- collision-resistant operator-scoped Kubernetes and Temporal namespace rendering;
  simple lowercase DNS-safe operator IDs remain readable, while case changes,
  lossy normalization, or truncation add a deterministic SHA-256 suffix, and
  that exact scope also owns the operator-local runtime state root
- source-controlled Security approval provenance and complete consumed-authority
  revalidation before every internal runtime script mutation
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
