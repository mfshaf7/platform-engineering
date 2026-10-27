# Operate the complete Console runtime

## Automatic artifact integrity and recovery

This extension is staged until exact Security acceptance. After accepted source
landing, commission its root-owned finite helper once, then activate normally:

```bash
make governance-console-complete-runtime ACTION=install-integrity
make governance-console-complete-runtime ACTION=activate
```

Installation uses existing Windows/WSL administration; no containerd socket,
credential, daemon or root arguments are exposed to Console/OOS/models. Admission
is local namespace/repository scoped. Startup checks installed code/policy hashes
against accepted source; updates require deliberate reviewed reinstallation.

Startup checks unpacked image inventory/bytes against digest-verified OCI layers.
Missing compressed layers may be fetched only from the exact public digest,
without operator registry credentials or tag upgrades. Cached baselines avoid
repeated decompression; mismatches regenerate independent verified baselines.

The existing maintenance timer uses cheap pod/frontend failure signals. Healthy
ticks do not scan images. For proven corruption, wait for owner work and pending
Helm rollback, plan all shared users, preserve controller UIDs/replicas, pause
affected managed consumers, refresh the identical cache and verify new bytes.
Persistent volumes, databases, accounts, credentials and source work are not
reset. Resume only through the retained supervisor; native normal readiness
closes the incident. Unknown faults get one scan, not speculative restart loops.

For corrupt frontend output, stop the managed frontend, quarantine derived cache,
rebuild exact clean accepted source/toolchain without credentials and verify its
native process/artifact. Failed/uncertain attempts latch across restart. Later
new incidents can repair after successful confirmation; this is not a lifetime
attempt cap.

Inspect with:

```bash
make governance-console-complete-runtime ACTION=check-integrity
make governance-console-complete-runtime ACTION=status
journalctl --user -u governance-console-repository-credentials.service -n 30
```

Private complete-runtime `artifact-recovery.json` and `receipts/` retain phase,
reason and evidence. Root state is
`/var/lib/platform-engineering/runtime-integrity`. Existing Platform capability
reasons expose recovery blocking. Integrity success alone does not prove owner
data or readiness healthy.

For a latched attempt, preserve journals and inspect exact bytes, root incident
and consumer/owner state through the same administrator path. Do not delete
journals or blindly replay uncertain effects. Unmanaged users, unsupported
controllers, retained shared snapshots, unavailable upstream and failed verified
replacement are operator-required. Host executables, mutable data and unique
source have no generic automatic overwrite permission.

Rollback uses reviewed admission with `automatic_repair` disabled and deliberate
reinstallation, or restores prior accepted source/decision. Preserve data and
evidence. This software cannot guarantee recovery from corrupted verifiers,
mutable data or an unavailable host.

This is the primary Platform operator surface for the complete local
Governance Operations Console runtime. It composes the existing
`refinement-catalog`; it does not create another runtime, workflow engine, or
authority plane.

The Console submits operator intent to OOS. OOS authenticates, persists, and
coordinates the bounded command. The Platform provider exposes only the
finite actions declared in `complete-runtime-policy.yaml` and performs effects
through the existing `dev_integration.py` owner command. Console and browser
processes never receive the Platform provider credential.

## Console capability completion

Epic1332 extends this same lifecycle; it does not create a second runtime or
workflow engine. Its source design is reviewed under Security1342. Final1345
must accept the exact validated Platform candidate tree and merged Console/OOS
sources before Platform merge or commissioning. The three operating stories
remain separate from source completion. Existing model selections, effort,
account custody and six-purpose baseline are preserved.

The final composed Security YAML also selects the existing OOS activation
bundle with `durable_orchestration.manifest_path` and `manifest_digest`.
The committed path is fixed at
`docs/reviews/components/console-capabilities-1332/manifest.json`, with its ten
existing `records/<gate>.json` siblings in the Security owner. Platform
publishes those original bytes privately under the accepted-idea-delivery
profile's existing `orchestration-activation` directory. OOS mounts that
directory read-only at `/var/run/oos/orchestration-activation`; both roles
revalidate the exact digest, records, target, lifetime and identity. Source
presence, an active Temporal component or an environment switch supplies no
activation authority. Missing admission denies startup before runtime changes.

After the final decision lands, commission through the same commands:

```bash
make governance-console-complete-runtime ACTION=validate
make governance-console-complete-runtime ACTION=install-integrity
make governance-console-complete-runtime ACTION=activate
make governance-console-complete-runtime ACTION=status
```

The integrity installation accepts only the reviewed policy/helper through the
existing administrator path. The added WGCF worker repository stays within
that finite policy. Do not advance primary execution checkouts away from their
accepted source while waiting for paired acceptance. If staged source requires
a temporary supported source binding, retain the accepted checkout for renewal
until coordinated commissioning, then remove the override and prove normal
refresh. Final Security must bind both its YAML and matching prose source list.

Purpose requests and explicit operator review use Console **Model Operations**.
The same authenticated bound human can submit and review a caller-owned request;
the distinct Platform fulfiller receives no human operator binding. Current
registry projection is available before any transaction. The existing trusted
Gary source-authoring/review bridge implements approved source changes; it
does not become browser or model authority. Its primary source procedure is
[Model-profile lifecycle](../../../docs/components/governed-ai-gateway/operations.md#model-profile-lifecycle).
When producing merged readback, add
`--request-history-root "$HOME/.local/state/platform-engineering/governance-console-complete-runtime/private/model-profile-requests/request-history"`
to publish the exact immutable history bundle. Send only that readback's
`oos_fulfillment` through the existing admitted fulfiller. Publication alone
does not complete the request: Console still requires canonical OOS applied
fulfillment and matching receipts. Reuse the identical original readback on an
uncertain acknowledgement; do not generate different historical timestamps.
Publish the current registry after the actual reviewed change and after
baseline restoration. Retain earlier request files; later source never replaces
an earlier request's source evidence.

Runtime observations use a separate
`governance-console-observations.service` oneshot and
`governance-console-observations.timer`. Collection has its own nonblocking lock,
ten-second per-command timeout, eighty-second service bound and256MiB memory
limit. The timer schedules collection thirty seconds after the prior collection
finishes. Its files are private under `private/runtime-observations` in the
same complete-runtime state root. Both runtime and Portfolio consumers are
wired from this producer. There are still exactly six admitted component
observations and the existing120-second validity window; other products remain
explicitly unknown. A failed collection leaves previous bytes unchanged for
honest expiry. Credential renewal never holds the observation lock or refreshes
its timestamps. Inspect the timer and journal, repair the existing dependency,
then let the next collection recover; do not extend TTL or synthesize health.

Normal `ACTION=restart` preserves the original valid bundle, digest-derived
queue, run IDs and history. The actual worker projections and current bundle
must agree; a ready Deployment alone is insufficient. Run creation, reads,
retry and cancellation use the existing Console/OOS workflow surface. Native
operating1346 must prove original-run continuity through worker loss/restart.

Intentional rollback, cleanup or teardown first retires an admitted generic
generation. The adapter drains OOS API start ingress and its ordinary workflow
poller, verifies their pods are gone, issues the existing fifteen-minute
Platform retirement manifest, and runs the existing OOS `retire` command in a
bounded owner job with only worker configuration and scoped retirement keys.
OOS seals and reconciles the original registry; Platform verifies its signed
receipt using the existing retirement verifier. Only then are execution grants
withdrawn. Retained requests, receipts, queues, business history and WGCF data
are preserved. A subsequent activation needs fresh accepted bundle authority;
a retired digest cannot be reused.

If interrupted, preserve the original job and
`.dev-integration/accepted-idea-delivery/<operator>/orchestration-retirement/<digest>/`
evidence. Retry the same lifecycle action while that authorization is current;
it reconciles the same job and receipt. An expired authorization, failed job,
incomplete key setup or invalid owner receipt requires reconciliation through
the existing [Temporal generation-retirement procedure](../../../dev-integration/profiles/temporal/README.md#initial-proof).
Do not delete uncertain state, invent a successful receipt or restart a sealed
generation. Inability to prove retirement blocks rollback completion.

## Security gate

Source validation is expected to report `security-pending` before work item
`#1319` lands. Activation remains blocked in that state.

Security owns these two files in `security-architecture`:

- `docs/reviews/components/2026-10-24-configurable-ai-routing.md`
- `docs/reviews/components/2026-10-24-configurable-ai-routing.yaml`

The YAML decision must accept gate `gate:ai-routing-composed-security`, work
item `#1319`, the current Architecture Packet reference, the exact reviewed
revisions for Console, OOS, Platform, Workspace Governance, WGCF, Prototype
Studio and CGG, and the
exact reviewed Platform tree. The Markdown review must contain those same
bindings. Runtime reads the decision from current clean Security `origin/main`
and materializes private policies; no post-review Platform source-pin edit is
required.

The decision retains the original reviewed candidate revision and exact tree.
After strict source acceptance, runtime readback and the active marker bind the
actual selected execution revision. A squash merge with the same accepted tree
can therefore operate without a post-review source-pin edit. Changed or dirty
source still fails acceptance; a later different provider revision cannot reuse
the earlier validated active marker.

## Model management extension

Epic 1313 extends this same composition. Candidate source is staged until the
exact Security decision and commissioning; these instructions do not assert
that a dedicated provider account is already signed in or any model is ready.
The existing Platform-operation, repository, publication and source-acceptance
boundaries remain part of the complete-source review.

Use the existing `make governance-console-complete-runtime ACTION=activate`
after acceptance and exact source landing. The existing GitHub Actions/GHCR
publication pattern supplies the fixed Codex 0.163.0 executable in the pinned
Python base. The `Build Governed AI Runtime` workflow runs only on main and
publishes `ghcr.io/mfshaf7/governed-ai-runtime` with an input-derived tag.
Activation pulls that artifact, checks its source/input labels, exact base
layers and executable digest, and resolves the immutable registry digest before
issuing new account credentials. Kubernetes pulls that digest through its normal
node runtime. The model-management adapter never gives a product/container the
host containerd socket. The separately admitted integrity helper above is the
finite Platform-owned cache maintenance path. Local `build-image` remains source
proof and does not publish or deploy.

The first GHCR package publication defaults to private. Its owner must make
this public, credential-free runtime package readable before commissioning;
verify anonymous access rather than importing an ambient registry credential.
This package contains only the accepted public base and executable, never
provider accounts or project files. A failed or unavailable publication blocks
activation before new credential effects. After setup, image reuse and normal
runtime restart require no administrator image import. The artifact identity
depends on its binary and base inputs; unrelated Platform record changes do not
create another image. Changed executable/base inputs still require source and
Security review before commissioning.

The existing gateway state volume is retained. The gateway runs as UID 1000 with
a read-only root, no service-account token or project mounts, a 1 GiB memory
limit, one CPU and bounded temporary storage. Native provider processes and
local model inference retain their existing single-slot limits. Management
reads and readiness never infer or claim ongoing provider entitlement.

The managed gateway uses a single-writer Recreate cutover. Before serving, its
nonroot startup preserves the exact legacy audit bytes and, where the previous
root-run container owned the file, atomically hands that file to UID1000 using
the volume's existing directory-write permission. No root container, recursive
ownership command or deleted history is needed. Unsafe or unwritable audit
storage prevents startup; later loss of private append storage withholds
readiness and inference before provider dispatch. Existing uncertain invocation
identities remain retained. Use their owner readback; never replace them with a
new successful receipt or silently dispatch another turn after recovery.

Only the gateway gains public IPv4 TLS egress plus the exact Vault service;
private ranges stay excluded from public egress. Existing DNS and declared
Ollama access remain. OOS and the consumer probe retain gateway-only provider
access. No direct external-provider route is granted to Console or consumers.

The dedicated Codex account is serialized with native refresh and sign-in.
If another request owns that account before a model turn is submitted, routing
reports `provider-busy` and may use only the operator's explicit configured
fallbacks. With no suitable fallback it fails closed. An error after dispatch,
account persistence, or account cleanup cannot become this availability result
or authorize another provider. Replaying the original invocation retains its
original frozen result, including uncertainty, after the account becomes free.

Platform creates a periodic Vault service token limited to read/create/update
of `kv/data/components/governed-ai-gateway/dev-integration/codex-account`.
Its intended token identity is persisted before issuance, so an interrupted
response reconciles that same identity. Only the gateway receives this token.
The native account is created through Console sign-in; activation never imports
the interactive CLI/Desktop account. The existing credential timer renews the
account lease; unavailable renewal fails visibly and does not widen authority.

A different management token is projected to OOS and the gateway. It authenticates
the fixed OOS/operator pair and grants only the closed model-management API.
Provider tokens never enter Console, OOS, source, receipts or process arguments.
The OOS caller binding is exactly `governance-operations-console` to the admitted
human operator. Its request journal reuses the existing private OOS state mount.

After activation, open Console Model Operations, register an admitted backend,
connect its dedicated account if needed, discover and verify a model, then
review default/task routing, native effort and explicit fallback. The Console
product's [operator procedure](https://github.com/mfshaf7/governance-operations-console/blob/main/docs/product/model-operations-live-integration.md)
owns those controls. Permission/data/output changes still require purpose-profile
review. Public/internal proof does not qualify private client data or stage/prod.

`ACTION=status` requires a current authenticated model registry, not a previous
completed model request. It reports API availability and verified registrations;
actual invocation and selection receipts are the separate operating proof.
Model verification bounds inventory/version metadata separately from model
output. A larger installed inventory does not consume the small verification
response budget; metadata still fails closed above the 1 MB catalogue bound.
The exact accepted source must be reaccepted and commissioned after an adapter
repair; do not replace the running module or edit a retained registration result.
`rollback`/`cleanup` first stop renewal, disable both management bindings, revoke
the account lease and remove its projections and added egress. Configuration,
invocation history and the Vault account are retained. Reactivation reuses that
owner state. Source rollback restores the preceding reviewed composition; do not
delete owner records to repair a runtime failure.

After merge, persistent services use the workspace main checkout when its
clean committed tree matches the reviewed worktree and `origin/main`. This
keeps the provider and composition auto-resume unit available after the
review worktree is retired. A different or dirty tree is never substituted.
Before removing the review worktree, activate from the current main checkout
and verify both services' `WorkingDirectory` and `ExecStart` paths:

```bash
systemctl --user show governance-console-platform-operation-provider.service \
  workspace-devint-accepted-idea-delivery-mfshaf7.service \
  -p WorkingDirectory -p ExecStart
```

Every referenced source directory must survive cleanup. Successful branch
cleanup alone does not prove runtime restart readiness.

That private activation policy enables WGCF's read-only workspace-continuity
projection only for the exact reviewed composition. It reuses the existing
server-side Console WGCF caller credential and removes the enablement during
rollback; neither the browser nor Console receives a new credential.

The same accepted composition activates repository provisioning through the
existing `gate:repository-custody-runtime-activation` boundary. Platform reads
the dedicated GitHub App private key from its existing Vault path, uses the
existing repository-provisioning identity tool to mint and project one
short-lived organization installation token, activates WGCF custody readiness,
mounts operator-private OOS custody state, and writes only the policy and
credential-binding references into the Console server environment. The token
and private key are never written to source, receipts, browser state, or
process arguments. The operator running activation needs a current private
Vault token in `VAULT_TOKEN` or mode-`0600` `~/.vault-token`.

The existing user-systemd lifecycle maintains provisioning and the five
previously commissioned Proposal Target, Prototype Landing, Prototype Maturity,
Prototype Closure and Workspace Intake identities. The existing
`governance-console-repository-credentials` unit names remain compatibility
names for this one timer; no new renewal service is introduced. Only the closed
App/installation set and the existing dedicated identity contracts/Vault paths
are allowed. Missing or disabled owner bindings require their existing
commissioning procedure; renewal cannot activate a workflow or widen scope.

The timer checks every minute and renews credentials when fewer than twenty
minutes remain. It also refreshes the two fixed canonical-record authorities
described below; ordinary record refresh does not rotate credentials or roll
out workloads. It reuses exact-App provider validation, checks current Security/source
bindings, and verifies the existing Secret ownership and credential binding.
All required Vault keys are checked before replacement. Resource-version
compare-and-swap uses the original identity producer's server-side Apply field
manager, preserving its recovery command and unrelated Secret fields. Native ownership proof is available without provider
issuance or real Secret changes:

```bash
CONSOLE_NATIVE_KUBE_PROOF_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  python3 products/governance-operations-console/scripts/test_console_complete_runtime.py
```

The existing local-cluster/session guard must pass; only uniquely named synthetic
ConfigMaps and synthetic Secrets are created and removed. This reproduces the old
replacement conflict, then proves each actual adapter's recovery compatibility,
stale-version denial and the existing producers' real Secret manifest format.
Temporary private keys are removed on every exit; tokens never
enter process arguments, logs, source, browser state or receipts.

The token batch takes one OOS delivery-version update and bounded rollout.
Unchanged versions do not restart OOS. After a crash between replacement and
consumption, renewal first consumes the retained version instead of minting
another. Readiness proves exact configuration, hash equality with each actual
mounted token, live provider acceptance and exact-one-repository scope. Prior
tokens are revoked after replacement consumption is proven. A process loss
before revocation can leave an old unchanged-scope token valid only until its
original maximum-one-hour expiry. Successful renewal requires normal revocation.
Missing Vault access, stale acceptance, failed consumption or provider denial
remains a visible failure, never readiness or ambient-credential fallback.

Landing, Maturity and Closure also consume the already-admitted WGCF OOS
registry caller. Their dedicated GitHub Apps remain separate; they do not
define separate WGCF principals. Renewal verifies the active operator WGCF
session, exact API credential binding, enabled owner gates and actual issuer
consumption before reconciling only their declared `wgcf-caller-secret` keys.
The same grouped rollout binds all three consumer issuer expectations to the
exact WGCF revision in the current Security-accepted composition. Historical
identity activation refs remain immutable foundation evidence; they are not
the current receipt issuer. The actual running WGCF image revision must match
the accepted one before any consumer reconciliation. OOS retains its exact
issuer and service-identity checks; no revision wildcard or ancestry waiver is
introduced.
The same exact issuer binding is maintained for the existing Workspace Intake
and Product Publication consumers. Their enablement, caller privileges and
Security gates do not change. Whole-process inspection covers all current
issuer expectations rather than treating the first failing workflow as the
entire dependency boundary.
This neither creates nor rotates a WGCF principal. A source mismatch fails
before replacement; the existing issuer commissioning path owns its repair.
Caller-only changes do not mint new GitHub tokens. Secret resource versions
join the existing delivery markers so one grouped OOS rollout consumes a
changed environment binding, including after interrupted delivery. Unchanged
markers leave the pod template unchanged. Status additionally verifies exact
OOS caller consumption and authenticated, non-mutating WGCF readiness reads
for all three families; valid provider tokens alone are not workflow health.
Credential values never enter arguments, output, receipts or the browser.

## Existing Product Publication binding

Complete activation preserves the already commissioned OOS/WGCF Publication
composition. It reads the exact reviewed OOS manifest and verifies the existing
owner enablement and the same accepted Publication Security decision before
continuing. It does not enable a disabled owner. The allowed targets remain
`unlisted`, `internal` and `archived`; this adds no client/public exposure.

The ordinary Console environment writer projects only the four existing
server-side Publication metadata fields from the accepted source policy:
reviewed Workspace Governance baseline and Security decision URI, digest and
revision. All existing caller, session, custody and Preview bindings remain.
Metadata is validated before replacing the private environment; it carries no
new credential and is never a `NEXT_PUBLIC_*` value. Each new Console command
independently reads current Inventory authority through the native Registry
reader. Historical Publication GETs retain their original authority and receipt.

After activation, `status` requires the actual Console Publication route to
report live mode, plus the existing OOS and WGCF bindings. A healthy homepage
or disconnected preview does not pass. Use the Console Publication procedure
for actual product writes and original-request recovery; a Platform status
receipt is not proof that a product was published. Restart uses the same
projection. Existing rollback removes the Console environment without deleting
or rewriting native owner journals, product state or their independent gates.
Do not run the legacy dedicated commissioning activation over the complete
composition to recover missing Console metadata.

For an active source-only public product, the existing generated source
projection can read a later merged canonical main without requiring an operator
to update the host checkout. It reuses the fixed-host anonymous provider
observer and exact provider identity, fetches only into its attributed generated
clone, requires forward ancestry from the clean local source and the existing
regular-file/size limits, and never executes app source. A changed main during
fetch, history rewrite, unsafe tree or unavailable provider removes Publication
freshness while preserving verified physical presence. The host checkout,
ignored data, source credentials and work-session resources remain untouched.
An unchanged unexpired observation retains its original short validity; local
timer ticks cannot renew remote freshness.

## Reviewed execution and current records

Execution code, schemas, workflow policy, model selection and owner commands
stay bound to the exact reviewed source. Platform maintains separate private
Git snapshots for only Workspace Governance and Prototype Studio. It fetches
their fixed canonical `main` refs without pulling or rewriting the primary
checkouts. Source/data classification is closed in
`scripts/console_record_authority.py`: inventories and owner records may
advance; Studio application source under `prototypes/` is incubation data to
this control plane. Landing's documented synthetic fixture outputs under
`fixtures/prototypes/<prototype-id>/` advance with those owner records, including
its empty `.gitkeep`; unrelated fixture namespaces remain outside the boundary.
Fixture data is never executed as control-plane code. Governing code, schema, policy, hooks, symlinks, executable
modes, history rewrites and unrelated paths are denied.

Unchanged refresh keeps the still-valid prior checkpoint readable while the
provider fetch and admission checks run, then replaces it atomically. A changed
record revision or reviewed source set invalidates the prior checkpoint before
changing the clone. Failed observation still invalidates freshness; this is not
an offline cache or grace-period bypass.

Each successful bounded refresh atomically issues a five-minute checkpoint
binding owner, trusted ref, reviewed control baseline, actual record revision,
observation and expiry. OOS and WGCF consume read-only snapshots and require
fresh checkpoints; the existing fixed Studio Preview adapter checks the same
binding independently. A failed refresh invalidates the entire two-owner
group, blocks authority-dependent writes and remains visible. It must not skip
existing credential renewal. Dirty or unique cache contents are preserved,
never reset. The next valid timer tick can recover without manual `git pull`.

The same minute refresh also projects physical source-only owners selected from
the fresh WG Intake/Inventory snapshot. A proposed or admitted entrant, or an
active owner, needs explicit provider identity and owner-local validation. A
matching clean canonical host `main`, exact provider origin and regular owner
guidance are required before a committed-source clone appears under the fixed
read-only WGCF `/sources` parent. Existing specific WG, Studio and Console
mounts remain unchanged. This exposes neither the whole host workspace nor
ignored app files, host Git credentials or runtime directories. No per-owner
code repin, manual clone or workload rollout is needed after native bootstrap.
Missing/unready owners remain absent; admission must still prove their controls.
Only attributed generated snapshots are moved out of the visible cache when
obsolete. Dirty/unattributed snapshots are preserved and fail closed, never
reset or deleted. Ordinary record/credential renewal retains its original
authority and credentials; source visibility is not app or runtime acceptance.

Once native Inventory registers an active product with a typed active
source-only owner, the same projection can supply Publication's committed
owner manifest. It anonymously verifies the exact public provider repository
and canonical `main`, and atomically adds observation/expiry to the existing
owner-attribution marker. No new mount, service or manual owner-root map is
needed. The existing five-minute observation may be reused only for the same
clean source/provider binding; unchanged local timer ticks never extend its
expiry. Near expiry, a fresh provider observation is required. Provider denial
or an unavailable, rewritten or unsafe canonical source removes Publication
freshness while preserving valid physical source presence. A clean older host
checkout can seed the generated clone; verified later public main is read only
inside that clone, without requiring host checkout alignment. Intake-only or unregistered-product owners retain
presence-only markers. The WGCF consumer independently checks current
registration, provider/custody attribution, freshness, regular Git source and
manifest ancestry; a local directory alone is not authority. This is the
public synthetic source qualification, not private/client source admission,
application execution, hosting or operational acceptance.

The Ollama runtime version remains an exact integrity pin. After an operator
host update, compare its actual `/api/version` and selected model digest with
all active bindings before recovery. A version-only source correction preserves
the model, task permissions and fail-closed check, passes normal owner review
and exact-source Security acceptance, then uses the same activation command.
Do not downgrade host software or relax version equality to make startup pass.

Complete status now checks actual workload mounts, read-only flags, selected
profile and consumed deployment generations, then reads both Console primary
registers. A successful empty live register is valid; fixture data, missing
models and a merely healthy homepage are not readiness. Work Design and
governed source realization execute through Delivery's existing work session;
Prototype exploration and baseline approval do not replace Delivery execution.

The existing session principal and all current Console commissioning policies
must name the same accountable actor as the admitted native source profile.
For this operator that is `operator:mfshaf7`, not the historical generic
`operator:workspace-owner` reference. No role, permission or alias is added.
Activation rejects another selected dev-integration operator before effects;
status reads only boolean matches for the Console actor in the four existing
OOS operator maps (Agent Console, source work, Platform Operations and Product
Publication). A missing or mismatched map is not readiness. Activation rebinds
the already-commissioned Publication Console entry while preserving its other
callers and without enabling publication. Prior receipts keep their original
actor; they are historical evidence, not approval for a differently bound new
source intent. Original source requests already bound to the actual operator
are preserved unchanged.

The `source-realization-v1` profile reuses the admitted local Ollama model.
The gateway validates Platform's bounded structural output schema; OOS then
validates its stricter change-set semantics and exact operator digest
acceptance. Source merge alone is not runtime commissioning. Status must prove
the actual gateway profile is ready and the OOS realization flag is active
after the exact Security decision is accepted.

Prototype authoring reuses this source-realization composition and the existing
model through the separate `prototype-source-authoring-v1` caller/task. Its
active source configuration is proposed deployment state, not current runtime
authority. Keep Platform primary and the running gateway unchanged until the
fresh exact composed decision accepts the final Platform tree and all seven
implementation owners, including changed CGG. Then use the existing activation
path, which renders and starts the admitted composition's CGG and gateway
participants; no additional service or activation manifest is introduced.
Qualify the actual Prototype profile/readback and Console authoring route during
the final operating witness. A healthy Delivery profile alone does not prove
Prototype readiness, nor does Prototype become mandatory for every project.

Security acceptance still reads and validates current clean Security `main`.
Its stable provenance anchor is the last commit touching the four relevant
decision/review files, not an unrelated generated-index commit. Changed or
revoked decisions change the anchor; no cached acceptance can override them.

The timer requires the active-runtime marker and uses the lifecycle lock
without waiting. Activation, restart, proof, and rollback therefore cannot race
renewal. Rollback stops renewal before revoking the token. Source-only review
does not prove renewal; commissioning forces the complete identity group through
the same refresh path and checks
the active timer and restored readiness. The owner recovery command remains
`ACTION=restart`; routine renewal requires no Console operator or CLI action.

## Everyday frontend, development and memory

Normal activation builds the exact clean Security-selected Console revision
in a private isolated source export, using locked dependencies and no live
caller, session or provider configuration. The existing Console user service
serves its standalone artifact. Every required static asset is copied; source,
Node version and the complete code-file inventory are validated before start
and in owner status. A changed, incomplete or foreign artifact fails closed.
The served artifact remains separate from editable source and `.next` output.

The build uses a4096MiB Node heap ceiling, one bounded build command at a time,
and kills the compiler process group on failure or timeout. The normal frontend
uses a2048MiB heap ceiling, systemd MemoryHigh3GiB, MemoryMax4GiB and at most1GiB
swap. Three rapid failures stop automatic retries. These are containment limits,
not an assertion of normal usage; commissioning records cold/warm peaks and
verifies representative operations remain below them.

For editing, use the normal reviewed source worktree and locked dependencies.
Start `node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 4317`
from that separate worktree. Keep its `.next` and dependencies separate from the
always-on artifact. Ordinary hot reload remains available. A disconnected
preview has no owner authority; authenticated integration still uses the
existing exact composition and private configuration, never credentials copied
into source or browser state. Publish a tested update through the existing
source, Security and activation path. No rebuild occurs on every ordinary
Console request.

Retain the prior source and artifact for the existing accepted-source rollback
and activation procedure. Runtime `ACTION=rollback` stops/revokes the frontend
boundary while preserving backend records; it does not silently restore an old
source decision. Restoring prior execution source follows the normal exact
Security decision and activation path. Credential refresh does not build the
frontend or replace its code. Restart reuses and verifies the selected artifact;
failed preparation leaves the current frontend untouched. Inspect private
`.building-*` logs after a failed build; preserve unexplained evidence and
remove only proven disposable build exports after diagnosis. Do not disable
source acceptance, type checks or functionality to meet a memory target.

WSL available memory, cache/pressure and Windows vmmem working set are separate
measurements. Cache reclamation eligibility and an appropriate VM ceiling must
be verified at the host boundary; setting a flag that is already the default
is not evidence of reclaimed host RAM. Required Console dependencies remain
running. Host settings that require WSL restart are activated only after the
existing restart-readiness checks and retained recovery state are ready.

## PC and WSL restart recovery

Recovery reuses the existing operator-login composition service. It is not a
pre-login or hardware-fault availability guarantee. The Windows bootstrap must
start the selected WSL distro, Docker Desktop must be running, and user-systemd
must be available for the configured operator.

Accepted activation waits up to120seconds for read-only Docker daemon and
Kubernetes API readiness before creating credentials, pulling runtime artifacts
or changing workloads. Each probe is bounded. Missing tools, unavailable
Security/source acceptance and exhausted dependency readiness remain explicit
failures; no identity or readiness bypass is introduced.

When a profile fails during startup, compensating teardown preserves the
composition recovery registration. The controller finishes its failure/degraded
record and the existing systemd retry policy applies: at most three starts in
ten minutes, sixty seconds apart. An intentional `down`/`reset` still removes
recovery registration. Repeated native crashes or permanently unavailable
prerequisites remain failures, never readiness. The start limit applies per
ten-minute window, not across the service lifetime; slow failures can continue
retrying across windows. Inspect the owner journal and archived profile action
result before another manual activation. Let an in-flight owner upgrade or
rollback finish before stopping the controller to prevent another retry. Credential renewal can report a busy lifecycle while
startup owns the lock and retries after that operation finishes.

Use normal `ACTION=status` after startup. It must prove current source/artifact,
consumed credentials and bindings, required owner projections and model registry;
a running frontend or healthy homepage alone does not prove restored operation.
Provider readiness must also match the exact accepted runtime version and
model digest. An automatic Ollama update can leave an eligible profile with
`provider-integrity-failed` even when the gateway is reachable. Compare bounded
provider metadata with `security/governed-ai-model-profiles.yaml`, reconcile the
existing binding through owner review and exact Security acceptance, then use
normal activation. Do not infer file corruption from that refusal or relax the
version/digest checks.

Preserve original application data and history during restart rehearsal. Source
and isolated fault-injection proof do not replace a real accepted-source startup
witness or an actual PC reboot observation.

## Commands

Validate source without changing runtime:

```bash
make governance-console-complete-runtime ACTION=validate
```

After the exact Security decision and all reviewed owner revisions are on
clean `main`, activate and inspect:

```bash
make governance-console-complete-runtime ACTION=activate
make governance-console-complete-runtime ACTION=status
```

Normal activation delegates before taking the lifecycle lock to the existing
admitted composition user service. Its product-owned drop-in invokes this same
complete-runtime activation, rather than only the raw profile launcher.
`Type=oneshot` and `RemainAfterExit=yes` retain owner helpers after the
controller exits. The finite Platform provider's start action uses this same
path. No additional daemon, service family or browser authority is introduced.
The Console web service restarts on successful unexpected process exit as well
as nonzero exit; an explicit systemd stop still leaves it stopped.

After writing the accepted active marker, activation also checks the existing
provider's exact Platform revision and finite executable capabilities. A
current provider is untouched, including a same-source start callback. A
stale provider is restarted once through its existing unit, then readiness is
polled for at most thirty seconds. Failure is explicit, not repeated restart
or successful activation. Status enforces the same exact catalog checks; an
old process saying `freshness: current` is not proof of current source.

Before activation changes runtime state, it verifies that Vault, OpenSSL, Git
and k3s resolve under the provider's controlled service PATH: the selected
operator's `.local/bin` plus the standard system binary directories. The unit
uses that same explicit PATH, not the caller shell or user-manager environment.
A missing tool stops activation before composition or credential effects. Keep
installed operator tooling in those directories; do not inject credentials,
alter global manager PATH or issue a replacement source scope to bypass a
missing tool. After recovery, reconcile the original Console source operation.

Recover the admitted services and re-prove current readback:

```bash
make governance-console-complete-runtime ACTION=restart
```

Run the bounded operating proof only during work item `#1291` commissioning:

```bash
make governance-console-complete-runtime ACTION=verify-operating
```

An uncached commissioning run must execute inside a retained user-systemd
oneshot with `RemainAfterExit=yes`; a temporary executor scope is rejected
before effects. The proof holds the lifecycle lock and calls its internal
activation directly, never a nested delegate that would deadlock. Inspect the
retained proof receipt and normal availability after the controller exits.

That proof checks authenticated startup, invalid-credential denial, revoked
gate denial, stale-marker denial, provider process-loss recovery, full restart,
rollback, teardown, repository-credential revocation, fresh credential
delivery and renewal, and restoration of executable Console repository provisioning. It
retains only credential-free receipts. The proof holds one operator-private
filesystem lock across the complete lifecycle. A replacement executor waits
on that lock and may reuse the result only when the retained receipt has a
valid content digest, the exact current Security decision and reviewed
revisions, the complete proof shape, and restored normal availability. Stale,
malformed, partial, or different-revision receipts are ignored and cannot
satisfy commissioning.

## Stop and cleanup

`rollback` revokes the short-lived repository-provisioning token, removes its
runtime Secret, removes Console-facing services and OOS/WGCF runtime bindings,
and preserves the existing composition and canonical owner state. `cleanup`
additionally removes generated credentials and private materialized policy.
`teardown` performs cleanup and suspends the complete composition.

```bash
make governance-console-complete-runtime ACTION=rollback
make governance-console-complete-runtime ACTION=cleanup
make governance-console-complete-runtime ACTION=teardown
```

Rollback and teardown never delete ART, Git, OOS workflow, WGCF, Security, or
owner evidence.

Rollback restores the original primary owner mounts, disables the new record
freshness and realization flags, removes only the product-owned composition
drop-in and preserves the generic profile auto-resume unit. Private record
snapshots and Studio Preview state are preserved; rollback does not rewrite
business history or reverse a reviewed owner merge.

The five other bindings predate the Console complete-runtime owner. Rollback
does not delete, disable or revoke them: their last dedicated tokens retain
their original bounded expiry while managed renewal stops. Teardown suspends
the existing composition. Later accepted activation renews stale tokens and
proves consumption; preservation does not promise indefinite availability.

## Failure interpretation

- `Security decision ... unavailable`: `#1319` has not landed at the declared
  path, or Security `main` is not current and clean.
- `missing, stale, revoked, or outside scope`: the decision does not accept
  this exact gate, initiative, work item, or Architecture Packet.
- `not the exact Security-reviewed source`: one owner checkout differs from
  the accepted revision, or the Platform tree differs from the reviewed tree.
- `active runtime does not match`: run `restart` or `activate`; do not edit the
  private policy.
- provider or Console readback unavailable: inspect the named systemd service
  and owner workload, repair the dependency, then run `restart`.
- `repository provisioning ... stale or mismatched`: refresh the Vault-backed
  activation with `ACTION=restart`; do not substitute an ambient `gh` token or
  browser credential.
- `Console repository provisioning is not executable`: inspect the reported
  WGCF, OOS, credential, state, and Console binding instead of bypassing the
  Repository Control surface.

Private state and receipts live below
`~/.local/state/platform-engineering/governance-console-complete-runtime/`.
Do not paste its private files into chat, ART, logs, or source control.
