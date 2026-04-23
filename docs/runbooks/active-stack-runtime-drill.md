# Active-Stack Runtime Drill

## Purpose

This runbook is the primary shared operator surface for the governed
`active-stack-runtime-drill` workflow.

Use it when you need to:

- capture the exact pre-drill local and live baseline
- bring the scoped runtime surfaces up through their existing owner commands
- verify the active mixed-lane stack drill with explicit evidence and blocker
  decisions
- restore the exact captured baseline afterward

This workflow is a temporary runtime exercise. It is not the same thing as:

- governed `stage -> prod` promotion
- source landing
- release approval
- a product-specific rollout runbook

## Machine-Readable Sources

The contract and evidence model live here:

- [../../environments/shared/runtime-drills/active-stack-runtime-drill.yaml](../../environments/shared/runtime-drills/active-stack-runtime-drill.yaml)
- [../../environments/shared/runtime-drills/active-stack-runtime-drill-evidence-template.yaml](../../environments/shared/runtime-drills/active-stack-runtime-drill-evidence-template.yaml)

The shared operator entrypoint is:

```bash
make platform-drill ACTION=<plan|snapshot|activate|verify|record|restore|status> PROFILE=active-stack-runtime-drill
```

The entrypoint runs:

```bash
python3 scripts/platform_drill.py <action> --profile active-stack-runtime-drill
```

## What This Workflow Owns

The shared drill workflow owns:

- the scoped drill contract
- the baseline snapshot
- the verification ledger
- the exception register
- the restore ledger
- the operator-facing evidence pack in each run directory

It does not replace the owner commands that actually activate or restore the
runtime surfaces. For example:

- devint surfaces still come up through `make devint-up`
- OpenClaw stage still uses `make openclaw-stage-state`
- OpenClaw prod still uses `make openclaw-prod-state`

Read this workflow as the shared control ledger around those owner actions, not
as a hidden all-in-one orchestrator.

## Current Scope

The current active-stack drill profile includes:

- accepted-idea-delivery devint runtime
- broker operator surface
- OpenClaw stage
- OpenClaw prod
- Vault
- External Secrets
- platform-postgresql
- platform observability baseline
- platform dashboards shared overlay
- host bridge surfaces required by OpenClaw

The current restore rule is:

- `exact-baseline`

That means restore is successful only when the in-scope surfaces match the
captured baseline or an approved recorded exception.

## Command Surface

Inspect the contract:

```bash
make platform-drill ACTION=plan PROFILE=active-stack-runtime-drill
make platform-drill ACTION=status PROFILE=active-stack-runtime-drill
```

Create a run directory and capture the baseline before any lifecycle change:

```bash
make platform-drill ACTION=snapshot PROFILE=active-stack-runtime-drill RUN_ID=<run-id> OPERATOR=<operator> NOTE="<note>"
```

Inspect a captured run:

```bash
make platform-drill ACTION=status RUN=<run-dir>
```

Record that live activation for a scoped surface occurred through its owning
operator path:

```bash
make platform-drill ACTION=activate RUN=<run-dir> ACTOR=<operator> SURFACE=<surface-id> NOTE="<what was activated>"
```

Record a verification result:

```bash
make platform-drill ACTION=verify RUN=<run-dir> CHECK=<check-id> STATUS=<passed|failed|blocked|not_applicable> ACTOR=<operator> EVIDENCE_REF="<evidence-ref>" NOTE="<note>"
```

Record a blocked verification with the required enterprise decision path:

```bash
make platform-drill ACTION=verify RUN=<run-dir> CHECK=<check-id> STATUS=blocked ACTOR=<operator> DECISION=<remove|workaround|accept-risk|defer> JUSTIFICATION="<why>" OWNER="<owner>" REVIEW_ON=<YYYY-MM-DD> EVIDENCE_REF="<evidence-ref>" NOTE="<note>"
```

Record additional evidence that does not belong to one verification check or
one restore surface:

```bash
make platform-drill ACTION=record RUN=<run-dir> PHASE=<baseline|activation|verification|restore|general> ACTOR=<operator> EVIDENCE_REF="<evidence-ref>" NOTE="<note>"
```

Record restore completion or an approved restore exception:

```bash
make platform-drill ACTION=restore RUN=<run-dir> SURFACE=<surface-id> STATUS=<restored|exception> ACTOR=<operator> NOTE="<note>"
```

Restore exceptions require the same enterprise decision fields:

```bash
make platform-drill ACTION=restore RUN=<run-dir> SURFACE=<surface-id> STATUS=exception ACTOR=<operator> DECISION=<remove|workaround|accept-risk|defer> JUSTIFICATION="<why>" OWNER="<owner>" REVIEW_ON=<YYYY-MM-DD> NOTE="<note>"
```

## Recommended Workflow

### 1. Plan The Drill

Run:

```bash
make platform-drill ACTION=plan PROFILE=active-stack-runtime-drill
```

Confirm:

- the scoped surfaces are the ones you intend to exercise
- the drill is truly a temporary runtime drill rather than a promotion
- the current evidence owner and restore mode still fit the exercise

If the drill model itself changed, route the review through:

- `security-architecture` for secrets, delivery, runtime, and host-control trust boundaries

### 2. Snapshot The Baseline First

Run:

```bash
make platform-drill ACTION=snapshot PROFILE=active-stack-runtime-drill RUN_ID=<run-id> OPERATOR=<operator> NOTE="<why this drill exists>"
```

This creates a run directory under:

- `.platform-drills/active-stack-runtime-drill/<run-id>/`

The directory is the operator ledger for the drill. It contains:

- `contract.yaml`
- `run.yaml`
- `baseline.yaml`
- `verification.yaml`
- `restore.yaml`
- `evidence.yaml`

Do not activate stage or prod first and capture the baseline later. That would
destroy the exact-baseline restore model.

## Scope Boundary

This workflow is not an estate-complete platform drill.

It covers the current operator-critical active stack across mixed lanes. That
means it can combine:

- devint surfaces
- shared control-plane surfaces
- stage product surfaces
- bounded prod surfaces

Do not call this workflow `full-platform` because it does not automatically
exercise every admitted environment or every possible product lane.

### 3. Bring Runtime Surfaces Up Through Their Owner Commands

The shared drill workflow does not directly activate the products or shared
components. Use the existing owner commands, then record that activation in the
drill ledger.

Examples:

- accepted-idea-delivery devint:

```bash
make devint-up PROFILE=accepted-idea-delivery
make devint-status PROFILE=accepted-idea-delivery
make platform-drill ACTION=activate RUN=<run-dir> ACTOR=<operator> SURFACE=accepted-idea-delivery-devint NOTE="accepted-idea-delivery devint converged"
```

- OpenClaw stage:

```bash
make openclaw-stage-state STATE=resume COMPONENTS=gateway,secrets,version
make platform-drill ACTION=activate RUN=<run-dir> ACTOR=<operator> SURFACE=openclaw-stage NOTE="OpenClaw stage rehearsal window resumed"
```

- OpenClaw prod bounded drill, only when the scoped exercise explicitly
  includes temporary prod exposure:

```bash
make openclaw-prod-state STATE=live CHANGED_BY=<operator> REASON=<reason>
make platform-drill ACTION=activate RUN=<run-dir> ACTOR=<operator> SURFACE=openclaw-prod NOTE="bounded OpenClaw prod drill enabled"
```

Use the product-local runbooks when the shared command alone is not enough:

- [../../products/openclaw/runbooks/manage-prod-lifecycle.md](../../products/openclaw/runbooks/manage-prod-lifecycle.md)
- [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
- [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)
- [dev-integration-profiles.md](dev-integration-profiles.md)

### 4. Verify The Drill Pack

The current contract expects evidence for these checks:

- `accepted-idea-delivery-runtime`
- `broker-operator-surface`
- `openclaw-stage-runtime`
- `openclaw-prod-lifecycle`
- `secrets-delivery-chain`
- `supporting-components-ready`
- `restore-attestation`

Record each result through `ACTION=verify`.

Examples:

- broker operator surface:
  - use the supported direct broker caller path from the active devint namespace
- supporting components:
  - use the owner commands and readiness runbooks for Vault, External Secrets,
    the platform observability baseline, and the platform dashboard overlay
- OpenProject and OpenClaw user paths:
  - use the owning access and release-governance runbooks, then attach the
    proof as `EVIDENCE_REF`

If a check is blocked, do not leave it as a bare blocked label. Record:

- `DECISION`
- `JUSTIFICATION`
- `OWNER`
- `REVIEW_ON`

That decision path is mandatory for enterprise drill evidence.

### 5. Record Supplemental Evidence

Use `ACTION=record` when the evidence matters to the drill but does not belong
to just one verification check or one restore surface.

Examples:

- baseline screenshots or exported status packs
- product UAT proof bundles
- stage/prod access transcripts
- operator sign-off notes

Those records are appended to both:

- `run.yaml`
- `evidence.yaml`

### 6. Restore The Exact Baseline

Use the owning commands to restore the live surfaces, then record the result
through `ACTION=restore`.

Examples:

- accepted-idea-delivery devint back to its captured posture
- OpenClaw stage back to its captured component set
- OpenClaw prod back to its captured lifecycle state
- the platform observability baseline and dashboard overlay back to their
  captured active or suspended posture

When a surface cannot be restored exactly, record:

- `STATUS=exception`
- the same enterprise decision path:
  - `remove`
  - `workaround`
  - `accept-risk`
  - `defer`

Do not call the drill restored while any in-scope surface still lacks either:

- `restored`
- or an explicit approved exception

### 7. Read The Evidence Pack

`evidence.yaml` is the operator-facing summary pack for the run. It is created
at snapshot time and then updated as you record activation, verification,
supplemental evidence, and restore outcomes.

It is not a replacement for the authoritative ledgers. Read the truth split as:

- `run.yaml`
  - run metadata and supplemental evidence record list
- `baseline.yaml`
  - captured local source state and runtime-surface baseline ledger
- `verification.yaml`
  - authoritative verification statuses
- `restore.yaml`
  - authoritative restore statuses
- `evidence.yaml`
  - operator-facing drill evidence pack that summarizes the run and exception model

Use:

```bash
make platform-drill ACTION=status RUN=<run-dir>
```

to inspect the current phase posture, pending checks, pending restore surfaces,
and exception count.

## Interpretation

Treat the drill as incomplete when:

- verification still has `pending` checks
- restore still has `pending` surfaces
- exception entries exist without a justified owner and review date

Treat the drill as only partially proven when:

- the products are reachable, but no evidence references were recorded
- the drill reached prod, but the exact-baseline restore proof is still missing
- the shared evidence pack exists, but the authoritative ledgers are stale or contradictory

## Related Docs

- [../standards/governed-runtime-drill-model.md](../standards/governed-runtime-drill-model.md)
- [../decisions/adr/ADR-014-governed-active-stack-runtime-drill-and-restore.md](../decisions/adr/ADR-014-governed-active-stack-runtime-drill-and-restore.md)
- [assess-environment-readiness.md](assess-environment-readiness.md)
- [dev-integration-profiles.md](dev-integration-profiles.md)
- [../../products/openclaw/runbooks/manage-prod-lifecycle.md](../../products/openclaw/runbooks/manage-prod-lifecycle.md)
- [../../products/openclaw/runbooks/release-governance.md](../../products/openclaw/runbooks/release-governance.md)
- [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)
