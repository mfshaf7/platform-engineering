# Governed Release Control Model

## Purpose

This standard defines the shared enterprise release-governance model for
moving governed workloads from source to stage to prod.

Use it when the question is:

- what release truth must exist before stage can be called ready
- what prod needs beyond a healthy runtime
- how products, shared control-plane components, and supporting components are
  supposed to participate in the same governed release system

This standard is about release control, not runtime state alone.

Use these related standards alongside it:

- [governed-runtime-lifecycle-model.md](governed-runtime-lifecycle-model.md)
  for `live`, `traffic-stopped`, `suspended`, and `quarantined`
- [release-model.md](release-model.md)
  for version pins, runtime drift, and rollback
- [ci-cd.md](ci-cd.md)
  for the CI or CD obligations that feed the release-governance model
- [workspace-governance/contracts/release-verification.yaml](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/release-verification.yaml)
  for the shared verification, readiness, and evidence-reference vocabulary

## Core Rule

Stage or prod is never ready from Argo health, pod readiness, or service health
alone.

A governed environment is only ready when the required workloads expose current
release truth for that environment:

- the exact candidate or deployed contract
- the matching verification evidence
- the matching readiness or support-readiness state
- the expected post-promotion verification state for prod

If those references are stale, incomplete, or missing, readiness must fail
closed.

## Release-Governance Tiers

The workspace uses four release-governance tiers.

| Tier | Meaning | Current examples | Stage requirement | Prod requirement |
| --- | --- | --- | --- | --- |
| `first-party product` | product with a source-owned governed artifact and promotion lane | `OpenClaw` | candidate, verification, readiness decision | deployed contract, post-promotion verification |
| `platform-integrated product` | product managed through the platform rather than an independent governed artifact lane | `OpenProject` | candidate, verification, readiness decision | deployed contract, post-promotion verification |
| `shared control-plane component` | shared service that materially shapes workflow, delivery, or approval behavior | `operator-orchestration-service` | candidate, verification, readiness decision | deployed contract, post-promotion verification |
| `supporting component` | shared dependency that participates in environment readiness without a standalone product promotion lane | `Vault`, `External Secrets`, `PostgreSQL`, `Observability`, `Dashboards` | deployed contract, verification, support-readiness | deployed contract, verification, support-readiness |

These tiers share one governance standard. They do not all use the exact same
operator workflow or file layout.

## Release-State Object Model

The shared object vocabulary is:

### Candidate

Immutable snapshot of the exact artifact and configuration set proposed for
governed stage rehearsal or release approval.

Minimum content:

- candidate status
- source refs
- artifact or contract refs
- required verification checks
- who recorded it and when

This object may come from:

- a source-owned build artifact lane such as OpenClaw
- a platform-owned release snapshot for a platform-integrated product
- a control-plane component release record

### Verification

Recorded rehearsal or validation evidence against an exact candidate or
component contract.

Minimum content:

- verification status
- candidate or contract reference
- who verified it and when
- evidence reference
- required check results

### Readiness Decision

Explicit approval or rejection decision for broader stage use or prod
promotion.

Minimum content:

- readiness status
- approved candidate or contract reference
- verification reference
- who decided it and when
- decision note

### Environment Contract

Git-managed desired deployed revision, digest, chart, and participating source
refs for one environment.

Minimum content:

- target environment
- deployed artifact or contract refs
- source refs
- who recorded it and when

### Support Readiness

Component readiness record used by aggregate environment readiness for
supporting components.

Minimum content:

- support-readiness status
- environment contract reference
- verification reference
- who assessed it and when
- note

### Post-Promotion Verification

Evidence recorded after the approved contract is live in the target
environment.

Minimum content:

- verification status
- deployed environment contract reference
- who verified it and when
- evidence reference
- required check results

## Verification And Readiness Vocabulary

The shared verification and readiness vocabulary is:

### Verification Status

| Status | Meaning |
| --- | --- |
| `inactive` | verification is intentionally inactive because the lifecycle or workload tier says it is not expected right now |
| `pending` | verification is required but no current acceptable record exists for the exact candidate or contract |
| `recorded` | verification is recorded for the exact candidate or contract with evidence and check results |

### Readiness Status

| Status | Meaning |
| --- | --- |
| `inactive` | the readiness decision is intentionally inactive for the workload or lane |
| `pending` | readiness approval is required and not yet granted |
| `approved` | readiness has been explicitly approved for the exact candidate and verification state |
| `rejected` | readiness has been explicitly denied for the exact candidate and verification state |

### Check Result Status

Use one shared check-result vocabulary across stage and post-promotion
verification:

| Status | Meaning |
| --- | --- |
| `passed` | the check succeeded |
| `failed` | the check ran and did not succeed |
| `blocked` | the check could not complete because of an unresolved blocker or missing dependency |
| `not_applicable` | the check does not apply to this workload or candidate and the catalog explicitly allows that outcome |
| `waived` | the check is not being enforced under an approved exception or accepted-risk path |

Do not invent workload-local result statuses when one of these already fits.

## Verification Catalog Contract

Every governed workload that uses stage verification or post-promotion
verification should publish a catalog that defines:

- check id
- category
- description
- capability tags
- whether the check is required by default in that context
- which result statuses count as acceptable in that context

Current shared rule:

- stage-readiness catalogs use `acceptedReadinessStatuses`
- post-promotion catalogs use `acceptedCompletionStatuses`
- catalogs must identify which checks are required by default in that context
  with the standardized `requiredByDefault` field

## Evidence Reference Contract

Every verification or post-promotion record must carry an `evidenceRef` that
points at operator-reviewable proof.

That evidence reference must:

- identify the exact candidate or environment contract that was exercised
- be durable enough for later audit or change review
- be reviewable without guessing which run, file, or ticket actually contains
  the proof

Accepted patterns include:

- repo-relative path to a dated change record or proof artifact
- cross-repo web-safe link to a Git-tracked evidence artifact
- immutable ticket, incident, or audit record reference
- immutable artifact-system reference with a stable identifier

Do not treat a vague note such as `tested manually` as evidence.

## Standard Stage Flow

Every governed stage lane should follow this order:

1. produce or record the current candidate or component contract snapshot
2. reset verification and readiness when that candidate or contract changes
3. rehearse the candidate in stage
4. record verification against the exact candidate or contract reference
5. approve or reject readiness explicitly
6. fail stage readiness closed if any required workload is stale, unverified,
   or missing the expected readiness object

The strongest current implementation of this pattern is OpenClaw:

- `environments/stage/release-candidate.yaml`
- `environments/stage/verification.yaml`
- `environments/stage/promotion-readiness.yaml`
  - retained OpenClaw product-local filename for the standardized stage
    readiness decision because that same record is the explicit promotion gate

That is the reference pattern, not the only allowed file layout.

## Standard Prod Flow

Every governed prod lane should follow this order:

1. promote the approved stage candidate or approved contract snapshot
2. update the prod environment contract in Git
3. reconcile the runtime through the governed deployment path
4. reset prod verification to the correct expected state for the new contract
5. record post-promotion verification once the target runtime is actually live
6. fail prod readiness or completion closed if the deployed contract and the
   prod verification state diverge

## Aggregate Environment Readiness

Environment readiness is an aggregate control over the workload-specific
release records that participate in that lane.

That aggregate control must:

- consume the exact governed candidate, verification, readiness, or
  support-readiness objects for each required workload
- fail closed if any required workload record is missing, stale, incomplete, or
  still in a non-acceptable status
- allow `inactive` only when the workload contract explicitly says that
  `inactive` is the correct current posture for that lane
- report which workload blocked readiness instead of collapsing everything into
  a vague health summary

The shared platform operator surface for this control is:

- `make environment-readiness ACTION=status ENVIRONMENT=stage`
- `make environment-readiness ACTION=validate ENVIRONMENT=stage`
- `make environment-readiness ACTION=status ENVIRONMENT=prod`
- `make environment-readiness ACTION=validate ENVIRONMENT=prod`

The current aggregate environment-readiness contracts are:

- `environments/stage/environment-readiness.yaml`
- `environments/prod/environment-readiness.yaml`

## Runtime Lifecycle Relationship

Runtime lifecycle and release governance are separate controls.

Examples:

- a workload may be `traffic-stopped` or `suspended` while still carrying a
  current deployed contract
- promotion may update the desired contract while the runtime lifecycle blocks
  user traffic
- prod verification may be `inactive` because lifecycle state says it should
  be, but the deployed contract still must remain attributable and current

Do not collapse lifecycle state and release readiness into one flag.

## Tier Expectations

### First-Party Product

Use the full product-grade flow:

- source-owned candidate
- stage verification
- stage readiness decision
- prod contract update
