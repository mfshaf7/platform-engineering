# Operate the complete Console runtime

This is the primary Platform operator surface for the complete local
Governance Operations Console runtime. It composes the existing
`refinement-catalog`; it does not create another runtime, workflow engine, or
authority plane.

The Console submits operator intent to OOS. OOS authenticates, persists, and
coordinates the bounded command. The Platform provider exposes only the
finite actions declared in `complete-runtime-policy.yaml` and performs effects
through the existing `dev_integration.py` owner command. Console and browser
processes never receive the Platform provider credential.

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
node runtime. Activation never accesses the host containerd socket or needs
sudo. Local `build-image` remains source proof and does not publish or deploy.

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
