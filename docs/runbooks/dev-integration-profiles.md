# Dev-Integration Profiles

This runbook is the primary operator-facing procedure for requesting and using
`dev-integration` profiles.

Use it when you need a fast local dev-integration environment for cross-repo
workflow or API iteration and want to know:

- whether an approved profile already exists
- how to launch and operate an approved profile
- how to request a new profile when no approved one fits

Do not reconstruct this flow from scattered contracts, templates, and
standards files. Those remain supporting governance sources, not the primary
operator path.

## Operator Lanes At A Glance

```mermaid
flowchart LR
    Request[Request or choose profile]
    Active{Active profile exists?}
    DevInt[dev-integration local lane]
    Promote[Promote-check and reviewed source change]
    Stage[Governed stage rehearsal]
    Prod[Governed prod]
    Proposals[Workspace Proposals]
    ART[Workspace Delivery ART]

    Request --> Active
    Active -->|no| Proposals
    Proposals --> Active
    Active -->|yes| DevInt
    DevInt --> Promote
    Promote --> ART
    Promote --> Stage
    Stage --> Prod
```

Read this as lane separation, not one blended environment:

- `dev-integration` is the fast local lane for changing workflow and API shape.
- `lane_class` declares the lane posture:
  - `prototype-devint` for prototype preview before graduation
  - `integration-devint` for workflow or API integration rehearsal
  - `governed-devint` for admitted governed component or workflow proof before
    stage handoff
- `Workspace Proposals` and `Workspace Delivery ART` remain the work-state
  systems of record while the local lane is active.
- `stage` is the first governed runtime rehearsal after reviewed source
  changes exist.
- `prod` comes only after the normal governed path, not from direct
  `dev-integration` promotion.

## 1. Check Whether An Active Profile Already Exists

The canonical registry is:

- [workspace-governance/contracts/developer-integration-profiles.yaml](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/developer-integration-profiles.yaml)

Only profiles with:

- `lifecycle: active`

are self-serve launchable from the shared runner.

Current active profiles:

- `governance-control-fabric`
  - owner repo: `workspace-governance-control-fabric`
  - lane class: `governed-devint`
  - profile path:
    [workspace-governance-control-fabric/dev-integration/profiles/governance-control-fabric/profile.yaml](https://github.com/mfshaf7/workspace-governance-control-fabric/blob/main/dev-integration/profiles/governance-control-fabric/profile.yaml)
  - role: local-k3s API, PostgreSQL, and isolated S3-compatible evidence-custody
    access for Governance Operations Console and WGCF contract iteration
  - storage actions: operator-scoped backup and confirmed digest-preserving,
    receipt-rebinding restore; server-assigned version IDs are superseded rather
    than falsely claimed as preserved; governed encryption and stage/prod use
    remain denied
  - destructive reset: `make devint-reset PROFILE=governance-control-fabric
    CONFIRM=reset-wgcf-evidence`
  - availability: storage-affecting actions are self-serve only while the
    active workspace registry binds the exact Platform acceptance, actions,
    and handoff checks declared by the owner profile; during ordered landing
    they remain dormant until the final registry change reaches `main`
- `idea-workflow`
  - owner repo: `operator-orchestration-service`
  - lane class: `integration-devint`
  - profile path:
    [operator-orchestration-service/dev-integration/profiles/idea-workflow/profile.yaml](https://github.com/mfshaf7/operator-orchestration-service/blob/main/dev-integration/profiles/idea-workflow/profile.yaml)
- `accepted-idea-delivery`
  - owner repo: `operator-orchestration-service`
  - lane class: `governed-devint`
  - profile path:
    [operator-orchestration-service/dev-integration/profiles/accepted-idea-delivery/profile.yaml](https://github.com/mfshaf7/operator-orchestration-service/blob/main/dev-integration/profiles/accepted-idea-delivery/profile.yaml)
  - role: persistent operator workbench for the local delivery ART lane
  - read-only smoke coverage: broker readiness, delivery draft validation,
    WGCF ART readiness configuration, optimized ART packet reads, and the first
    automated landing-unit closeout evidence read
- `accepted-idea-delivery-mutation-smoke`
  - owner repo: `operator-orchestration-service`
  - lane class: `integration-devint`
  - profile path:
    [operator-orchestration-service/dev-integration/profiles/accepted-idea-delivery-mutation-smoke/profile.yaml](https://github.com/mfshaf7/operator-orchestration-service/blob/main/dev-integration/profiles/accepted-idea-delivery-mutation-smoke/profile.yaml)
  - role: disposable mutating smoke companion for accepted-idea consume and backlink rehearsal

- `context-governance-gateway`
  - owner repo: `context-governance-gateway`
  - lane class: `governed-devint`
  - profile path:
    [context-governance-gateway/dev-integration/profiles/context-governance-gateway/profile.yaml](https://github.com/mfshaf7/context-governance-gateway/blob/main/dev-integration/profiles/context-governance-gateway/profile.yaml)
  - role: persistent local-k3s API, worker, PostgreSQL, MinIO, and PVC-backed
    custody lane for CGG service-mode context admission proof
- `governed-ai-gateway`
  - owner repo: `platform-engineering`
  - lane class: `governed-devint`
  - profile path:
    [platform-engineering/dev-integration/profiles/governed-ai-gateway/profile.yaml](https://github.com/mfshaf7/platform-engineering/blob/main/dev-integration/profiles/governed-ai-gateway/profile.yaml)
  - role: persistent local-k3s gateway API, provider-custody Secret, local
    audit ledger, consumer egress probe, and provider-sentinel denial proof for
    the governed AI access plane
  - launch rule: model-profile activation remains separately gated by the
    governed AI access-plane contract

If a suitable `active` profile already exists, use it directly. If not, follow
the request path in section 3.

For `governed-ai-gateway`, the operator selects the reviewed environment before
running the shared profile commands:

```bash
export DEVINT_GAI_MODEL_ENVIRONMENT=<reviewed-environment>
make devint-status PROFILE=governed-ai-gateway
make devint-up PROFILE=governed-ai-gateway
make devint-smoke PROFILE=governed-ai-gateway
```

The runtime resolves every reviewed profile for that environment. Each request
must select one exact profile, caller, task contract, output schema, and binding;
unknown, inactive, or mismatched selections fail closed without falling back to
another profile or provider binding. The shared smoke command exercises the
active intake compatibility profile, while the `refinement-catalog`
composition activates the independently reviewed
`delivery-refinement-advisor-v1` profile. The Console still cannot call the
gateway or Temporal directly.

Current active composition profile:

- `temporal`
  - owner repo: `platform-engineering`
  - lane class: `governed-devint`
  - request record: `openproject://work_packages/707`
  - profile path:
    [platform-engineering/dev-integration/profiles/temporal/profile.yaml](../../dev-integration/profiles/temporal/profile.yaml)
  - role: source-defined persistent local-k3s runtime adapter behind OOS for durable
    scheduling, replay, timers, waits, and activity retry dispatch
  - launch rule: self-serve local launch is allowed only through the active
    `refinement-catalog` composition after Security review #1012, Workspace
    activation #1017, Platform activation #1013, the operator-scoped Workspace
    binding, and successful merged-runtime rehearsal
  - controlled commissioning: the bounded proof remains non-self-serve and is
    unavailable until its issuer and executor are reviewed and an exact permit
    is approved; use the
    [Temporal controlled commissioning procedure](../components/temporal/operations.md#controlled-commissioning-proof)
    as the primary Platform operator surface
  - selected business definition: `delivery.refinement.apply` version `1` is
    active only through OOS-owned contracts and the composition-bound Temporal
    queue and worker identities

### Temporal Generation Retirement

When a prior OOS workflow generation exists, use the Platform-owned procedure
before suspension, replacement, or fresh activation:

1. quiesce OOS start ingress and prove zero active replicas and zero in-flight
   starts
2. prove zero ordinary OOS workflow pollers for both generated queues
3. issue the old generation manifest using observations no more than five
   minutes old and a lifetime no longer than fifteen minutes; the issuer derives
   both the business queue and durable start registry from the activation digest
   and pins the OOS Ed25519 receipt verifier, canonicalization, and signed
   content contract
4. run the explicit OOS retirement command, which verifies its receipt key,
   carries the exact manifest lifetime in an acknowledged seal
   Update-with-Start with a deterministic authorization-derived ID, requires
   the registry to validate that ID and handler time before mutation, seals the registry,
   reconciles and cancels exact registered workflow IDs, and starts the one-shot
   worker only after revalidating the manifest
5. verify the receipt signature, account for every registration, prove every
   matched run reached a terminal projection, and prove the one-shot worker
   started inside the manifest lifetime and within five minutes of both drain
   observations; retain it before issuing any fresh activation

The registry workflow accepts only the deterministic registration Update ID
derived from the business workflow ID. A full generation returns
`409 orchestration_generation_capacity_exhausted` and must be retired before a
fresh generation is activated. An expired seal Update returns
`seal-not-authorized` and leaves the registry open for a fresh authorized
retry. The verifier reproduces the versioned
canonical UTF-8 receipt bytes and checks them against the published
cross-language conformance vector.

The source-valid entrypoint is:

```bash
python3 dev-integration/profiles/temporal/scripts/generation_retirement.py --help
```

Use the exact command arguments and evidence rules in the
[Temporal profile procedure](../../dev-integration/profiles/temporal/README.md)
and the [Temporal operations guide](../components/temporal/operations.md).
Unexpected activation-evidence loss is an incomplete fail-stop fence; it is
never a substitute for this retirement procedure.

## 2. Use An Active Profile

Run the shared operator commands from `platform-engineering/`:

```bash
make devint-up PROFILE=<profile>
make devint-status PROFILE=<profile>
make devint-access PROFILE=<profile>
make devint-smoke PROFILE=<profile>
make devint-backup PROFILE=<profile>
make devint-restore PROFILE=<profile> BACKUP_FILE=<path> CONFIRM=<profile-confirmation>
make devint-promote-check PROFILE=<profile>
make devint-reset PROFILE=<profile> CONFIRM=<profile-confirmation>
make devint-down PROFILE=<profile>
```

When a workspace-registered runtime composition is required, use the same
shared lifecycle surface with `COMPOSITION` instead of `PROFILE`:

```bash
make devint-up COMPOSITION=work-design-advice
make devint-status COMPOSITION=work-design-advice
make devint-down COMPOSITION=work-design-advice
```

`PROFILE` and `COMPOSITION` are mutually exclusive. Runtime compositions are
limited to `up`, `status`, and `down`; run profile-specific access, smoke,
backup, restore, reset, and promote-check actions against the relevant profile
after the composition is healthy.

The shared runner validates every participant and required lifecycle, starts
providers before consumers, derives cluster-local service endpoints, and
projects only contract-declared environment variables. Endpoint projections
support URL and host-port formats. Caller bindings must name a declared
dependency edge. Literal, profile-service, operator-template, and
profile-namespace bindings must name an exact target profile and variable;
duplicate or ambient targets fail closed.
Runtime-generated
credentials live under the operator-private composition state root, never in
Git or command arguments. Repeated `up` reuses the active composition binding;
successful `down` stops consumers before providers and removes that binding.
An operator-template binding accepts exactly one literal `{operator}` token and
renders it from the same sanitized operator identity used by the composition.
It is not a general formatting language and cannot interpolate credentials,
profile data, or arbitrary environment values.
A profile-namespace binding projects the runner's already computed namespace
for one declared participant. Profiles must not reconstruct peer namespaces
from an operator string because the runner owns normalization and length bounds.
Failed start, status, teardown, ownership, lifecycle, credential, or projection
checks fail closed. Composition state reports identifiers and outcomes only;
it never records credential values.

Meaning:

- `devint-up`
  - creates, refreshes, or resumes the local profile runtime declared by the
    active profile
  - starts or reconciles every declared persistent host service only after the
    foreground owner action succeeds
- `devint-status`
  - shows the current session and runtime state
  - reports each declared host service's real PID, readiness, and log path;
    unhealthy declared services make the command fail
- `devint-access`
  - reports or opens the profile's primary inspection surface
  - disposable profiles may hold a foreground port-forward until you stop it
  - persistent profiles may use a platform-managed localhost mapping and
    return after reporting its health
- `devint-smoke`
  - runs the profile’s smoke checks
  - for persistent ART profiles such as `accepted-idea-delivery`, this must
    stay read-only while still proving the optimized broker packet and closeout
    evidence surfaces that operators depend on
- `devint-backup`
  - captures an operator-local backup when a persistent profile implements the
    optional backup contract
- `devint-restore`
  - restores an operator-local backup only for profiles that implement the
    optional restore contract and only with the profile's explicit confirmation
    value
- `devint-promote-check`
  - renders the profile-owned governed handoff checklist that must be proven
    before calling the local slice ready for `stage`
- `devint-reset`
  - tears down and rebuilds the local profile state
- `devint-down`
  - stops the profile runtime using the profile's declared state model

Profiles that need a process to survive after `up` returns use this bounded
shape:

```yaml
host_services:
  - id: example-reconciler
    command: dev-integration/profiles/example/scripts/reconcile-loop.sh
    readiness:
      mode: command
      command: dev-integration/profiles/example/scripts/reconcile-ready.sh
      timeout_seconds: 10
      interval_seconds: 0.25
      probe_timeout_seconds: 5
```

Both commands are owner-relative files resolved inside the selected owner
checkout. The service command must remain in the foreground; the shared runner
performs the detach and owns PID state, command-digest comparison, logs,
readiness, status, serialization, and teardown. The digest includes every
declared source repo revision, so changing imported or invoked source causes a
restart even when the entrypoint file itself is unchanged. Use `process`
readiness only when process liveness is the complete readiness claim. Do not
add profile-owned `nohup`, `setsid`, PID files, or duplicate stop logic.

Each dispatched action leaves a local manifest/result pair under
`.dev-integration/sessions/`. The result is self-contained: it records the
return code, source-manifest digest, and complete source manifest captured
before dispatch. The shared runner creates these read-only records only after
the owner action returns and its direct process group has been closed. The
runner creates each path exclusively and never overwrites an earlier record.
Owner actions still run with their declared host and cluster access; this is
not a security sandbox, and these local files are not protected evidence. Use
the record digests only as provisional local handoff inputs, never as
standalone completion or rollout authority.

Composed child actions leave the same per-profile manifest/result evidence and
also record their `runtime_composition_id`. The composition coordinator keeps
one private redacted state file under
`.dev-integration/compositions/<composition>/<operator>/`; this is local
runtime ownership state, not governed completion evidence.

Declared host-service state lives under the operator-scoped profile state root
at `host-services/<service-id>/`. `service.yaml` and `service.log` are runner
owned. Process ownership binds PID, Linux boot ID, and process-start ticks. If
status reports `identity-mismatch`, inspect the recorded state and host process
before retrying; the runner intentionally refuses to kill or replace an
unverified PID. A successful lifecycle action retires verified recorded
services removed from the selected profile; `status` reports such a service as
undeclared until that reconciliation occurs and omits its retired tombstone
afterward.

State-model rule:

- `disposable` profiles
  - `devint-down` may remove the live runtime entirely
  - use `devint-reset` when you want a full local wipe including profile state
- `persistent` profiles
  - `devint-down` must preserve project data and behave as suspend
  - `devint-up` resumes or reconciles the preserved runtime
  - use `devint-reset` only when you intentionally want to destroy the local
    project history and rebuild from scratch
  - shared `devint-smoke` must stay read-only on the persistent working lane
  - backup and restore are profile-specific optional actions; they do not
    become available merely because a profile declares persistent state
  - if a workflow still needs mutating smoke, run that proof through a
    separate disposable companion profile instead

Important boundaries:

- `dev-integration` is local only
- it is not governed rollout evidence
- it must not write to governed `stage` or `prod` backends
- owner and declared source repos may use local branches, worktrees, and dirty
  state; the runner records a working-tree SHA-256 for dirty sources so
  different local source bytes do not share one manifest identity
- the selected `platform-engineering` checkout that supplies the shared runner
  must be clean so its recorded Git head identifies the executing control-plane
  code exactly
- it still requires a governed handoff before `stage`
- the active profile README and `stage_handoff.required_checks` are part of
  that handoff contract, not optional notes
- persistent profiles are reserved working lanes, not mutation-smoke targets
- if a test would create or mutate local work-tracking artifacts, it belongs in
  a disposable companion profile rather than the persistent lane
- a profile's runtime platform is declared in its owner-repo
  `profile.yaml`; active profiles can use local k3s or another approved local
  runtime shape, but the profile's access and smoke scripts are the authority
  for how operators reach it

Access note for persistent OpenProject lanes:

- `accepted-idea-delivery` uses Windows `127.0.0.1:18183` mapped by
  `PlatformCoreHostStack` to its stable WSL NodePort `32183`
- the foreground port-forward remains a fallback, not the normal persistent
  access lifecycle
- run smoke on alternate local ports while keeping the canonical host header,
  for example:
  - `DEVINT_OPENPROJECT_LOCAL_PORT=28183 DEVINT_OPENPROJECT_HOST_HEADER=localhost:18183 DEVINT_BROKER_LOCAL_PORT=28180 make devint-smoke PROFILE=accepted-idea-delivery`

## 3. Request A New Profile When None Fits

If no suitable `active` profile exists, request a new one.

The request/admission contract is generic, but the current human request
surface adapter is OpenProject.

Current request surface:

- project: `Workspace Proposals`
- identifier: `workspace-proposals`
- access path:
  [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)
- canonical backlog contract:
  [../../products/openproject/idea-backlog-contract.md](../../products/openproject/idea-backlog-contract.md)

Recommended request record shape in the current adapter:

- type:
  - `Component Proposal` when one component repo clearly owns the profile
  - otherwise the proposal type that best matches the owner shape
- status:
  - `captured` or `triaged` while the profile is still `proposed`

Required request content:

- requested profile id
- owner repo
- purpose
- requested runtime state model:
  - `disposable`
  - `persistent`
- participating repos
- runtime dependencies
- expected canonical backend writes, if any
- requested runtime platform, such as `local-k3s`
- whether identity, secrets, runtime privilege, or AI review is involved
- requested by
- request record system
- request record ref

Additional required request content for `persistent` profiles:

- why `persistent` is needed instead of a disposable smoke lane
- what data must survive normal `devint-down` / `devint-up` cycles
- what suspend/resume behavior operators expect
- expected storage size or storage-class constraints
- what `devint-reset` is allowed to destroy
- cutover plan when upgrading an existing disposable profile into a
  persistent project-backed lane
- smoke mutation mode
  - persistent profiles must keep shared `devint-smoke` read-only
- disposable companion profile, when the workflow still needs mutating smoke
  - do not point mutating smoke at the persistent working lane

Supporting template:

- [workspace-governance/templates/dev-integration-request/README.md](https://github.com/mfshaf7/workspace-governance/blob/main/templates/dev-integration-request/README.md)

When the current adapter is OpenProject, record:

- `request_record.system: openproject`
- `request_record.ref: openproject://work_packages/<id>`

## 4. How A Requested Profile Becomes Launchable

A request is not the same thing as an approved self-serve profile.

The admission path is:

1. the request is recorded
2. the owner repo confirms the profile belongs there
3. `platform-engineering` accepts or rejects the shared-lane fit
4. `security-architecture` reviews it when the profile widens identity,
   secrets, runtime privilege, AI influence, or other risky boundaries
5. `workspace-governance` records the profile in
   `developer-integration-profiles.yaml`
6. the profile may become `build-admitted` when implementation is authorized
   but runtime launch is still denied
7. the profile becomes self-serve only when its lifecycle is set to `active`

Persistent-profile acceptance rule:

- `platform-engineering` must explicitly accept the persistent runtime fit,
  storage model, and suspend/resume semantics
- `workspace-governance` should not mark a persistent profile `active` until
  the request record and owner docs make the destructive-reset boundary clear

Lifecycle meanings:

- `proposed`
  - request exists, not self-serve launchable
- `build-admitted`
  - implementation is authorized after platform and security gates, but the
    profile is not self-serve launchable
- `active`
  - admitted and self-serve launchable
- `suspended`
  - admitted before, temporarily blocked from normal launch
- `retired`
  - no longer part of the active self-serve set

## 5. What Happens After Dev-Integration

`dev-integration` never promotes its runtime directly into `stage`.

The required handoff is:

1. run `make devint-promote-check PROFILE=<profile>`
2. turn the winning local shape into real source changes
3. run repo-local validation
4. move those changes through the normal PR and platform contract path
5. rehearse the governed candidate in `stage`

Additional rule:

- do not treat source landing as workflow closure when the profile still
  requires governed `stage` rehearsal
- if the landed workflow surface changed, update the profile-owned
  `stage_handoff.required_checks`, the profile README `Stage Handoff Checks`
  section, and the promote-check output in the same work

For the workspace-level PR flow and optional advisory-review procedure that
begins after step 4, use:

- [workspace-governance/docs/pull-request-review-and-automation.md](https://github.com/mfshaf7/workspace-governance/blob/main/docs/pull-request-review-and-automation.md)

Supporting standard:

- [../standards/dev-integration-lane.md](../standards/dev-integration-lane.md)
