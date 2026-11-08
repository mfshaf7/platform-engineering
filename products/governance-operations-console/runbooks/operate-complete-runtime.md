# Operate the complete Console runtime

## Connected GitHub accounts

The account-routing extension reuses this lifecycle, credential timer,
purpose-specific Vault custody and the repository-provisioning Secret. Review
source/preview first; only the existing exact composed Security acceptance and
normal activation may commission it.

The engineering selection is the existing complete-runtime state's
`private/repository-connections.json`, a private regular mode0600 file. Example
with synthetic IDs:

```json
{"schema_version":1,"default_connection_id":"github:example-company","connections":[
  {"account":"example-personal","account_type":"personal","grants":{
    "metadata":{"app_id":101,"installation_id":201},
    "provisioning":{"app_id":102,"installation_id":202}}},
  {"account":"example-company","account_type":"organization","grants":{
    "metadata":{"app_id":101,"installation_id":203},
    "provisioning":{"app_id":102,"installation_id":204}}}
]}
```

Connecting an account is explicit authorization. Verify native App installations;
an organization-private App cannot be assumed installable on a personal account.
Reuse an appropriately installable App or commission a separate App with the same
purpose and exact permissions. Optional `key_slot` selects a private key beneath
that purpose's existing Vault prefix `connections/<slot>`, with a bounded lowercase
identifier. Arbitrary key paths are rejected. Without it, reuse the existing key.
No key or token belongs in the selection, browser, command arguments or receipts.

The timer verifies App ID, account ID/login/type, suspension, events, exact role
permissions and native token lifetime. Metadata requires an approved All
repositories grant for future repositories. Provisioning retains the approved
native installation selection, including selected-repository installations;
it does not widen access. Optional lifecycle grants additionally name one
`repository` with `name` and decimal `provider_repository_id`: the token is filtered
and readback-verified for that one repository, preserving the existing maximum-one
scope. Account-wide lifecycle tokens are denied, and the separate activation gate
still applies. Source authoring retains its separately verified Source App.

Delivery rechecks the selection, uses Secret resource-version CAS, and reuses the
existing rollout/fingerprint probe. Previous in-memory tokens are revoked after
consumption; a crash leaves any unretired old lease bounded by native expiry.
Current ticks and restart reuse verified deliveries. Unavailable account/role pairs
are listed in the sanitized private delivery receipt and retried by the timer;
healthy connections remain usable. Inspect that receipt and the Console's
authenticated connection read. Credential currency is not proof of application
acceptance or of a still-authorized provider operation.

Changing the default changes only new form selection. Removing an account removes
it from the next consumed projection; native App suspension/uninstallation provides
immediate provider revocation. An explicit empty connection list/default null
disables account routing without falling back to legacy credentials.

Before packaged release, implement the existing Console provider-onboarding
requirement: after installation ask for personal accounts, organizations or both,
guide native authorization, verify connections and choose a default. Allow later
changes in one trusted installation with one private Registry. Current engineering
configuration does not qualify customer onboarding or require building an installer
in this maintenance batch.

## Private source and internal records — unpublished maintenance

Operator-approved maintenance extends the existing source controls to project
registrations held in installation-private operational storage. Landing Unit
decision `feature_single_landing_unit`, `maintenance-private-source-platform`.
This candidate is not runtime acceptance or permission to activate it.

Platform must independently read current installation-bound source eligibility
before issuing a project credential. Legacy Git admission keeps its existing
reader; native authority must not be represented as a fictitious Git record or
trusted from a caller-supplied digest. A distinct read-only Platform binding to
the existing WGCF authority endpoint must not grant registration writes, generic
record export or reconciliation.

Private inspection reuses the approved Source App, verifies its full installation
contract, then reduces the temporary token to Contents/Metadata read for exactly
one canonical repository. The finite bootstrap control-file allowlist, bounded
regular Git tree/blob checks and unconditional token revocation remain required.
The Metadata App, browser, ordinary model requests and public Studio records
must not receive private source contents or the token. Existing source write,
review, merge and revocation procedures remain the effect boundary.

The same protected provider exposes a separate source-authority inspection
read for the synchronous OOS host admission interface. It returns only current
registration eligibility and carries no source key, token, file content or
generic operation journal. It requires current accepted source and recovery
health, compares policy before and after the WGCF read, and denies namespace
substitution. OOS checks that policy against its own exact accepted cache bytes.
The separate finite checkout transport derives its managed destination beneath
`.worktrees/instance-sources/<installation namespace>/repositories/` and permits
only clone, fetch and exact branch-reference reads. The read token stays in
Platform, in a temporary private askpass file removed before return, and is
revoked on success or failure. No caller destination, URL, command or token is
accepted. Git failures and uncertain revocation preserve the checkout and
withhold completion. Native project files are never copied into public root
owner indexes or automatic model requests.

When the accepted policy explicitly enables `instance_records`, the existing
complete-runtime startup prepares one private `instance-installation.json`
before derived source-reader/host bindings. Retries retain the same identity
and source-reader secret; missing original state with retained derived bindings
blocks recovery rather than generating a replacement installation. The host
uses its existing authenticated OOS-to-Platform private CNI connection. Its
RFC1918 HTTP allowance applies only to that commissioned host connection.
After composition startup, the lifecycle verifies the existing WGCF migration
contains `0016_instance_records` (or a proven descendant), then projects native
flags and the distinct source-only read role. It uses the original OOS role for
registration writes. No per-project account grant or new database is created.
Do not enable this candidate before exact-source acceptance and batch review.

The approved publication selects `instance_records.enabled` in this installation's
canonical complete-runtime policy. Backend/native transport defaults still deny
an absent or disabled binding. This selection performs no activation: the policy
retains `security.status: pending`, and the normal lifecycle must verify the exact
landed source set, accepted Security decision and migration before commissioning
the private connections and native owner flags. Do not edit a running environment
or add a second policy overlay to bypass those checks.

Publication, exact-source Security acceptance, explicit composition activation
and a real operating witness remain separate later steps. This unpublished
preparation changes no live provider permission, service or business record.

## Backend connection recovery

Live and preview Console servers share the two existing loopback OOS/WGCF
connections. Their services supervise the tunnel child and probe `/healthz`
every ten seconds, with a two-second request timeout. Three consecutive
transport failures recycle only that child; initial startup has a twenty-second
grace. After cleanup, systemd waits five seconds before reconnecting. An HTTP
error is a responding backend, not proof of readiness and not a reason to
restart its working connection. No business operation is replayed.

After exact merged-source Security acceptance, install/refresh only these
connections without rebuilding the frontend, restarting owner workloads or
renewing credentials:

```bash
make governance-console-complete-runtime ACTION=refresh-connections
```

Normal activation/restart installs the same supervision. The command takes the
existing lifecycle lock and rejects unaccepted source. Its receipt proves only
connection liveness. It does not certify application or complete-system health.

Inspect `governance-console-cross-domain-oos.service` and
`governance-console-cross-domain-wgcf.service` with `systemctl --user status` and
`journalctl --user -u <unit>`. A repeated `Backend tunnel is unresponsive` line
records automatic recovery. A `Backend tunnel stream timed out` message also
records recovery when kubectl reports its specific stream-creation timeout while
health still responds. The same supervised connection is replaced; backend HTTP
errors and unrelated diagnostics do not request recycling. The stderr reader
uses bounded chunks, and no application payload is inspected. The supervisor
uses no provider/account credential,
does not follow health redirects/proxies and does not publish backend payloads.
Ordinary stop/rollback/suspension stops the supervisor and child together; no
separate timer restarts a deliberately stopped connection. Rollback selects the
previous accepted Platform/Security pair and runs its matching operator path.

The internal stream-freeze trigger remains unproven. Recovery prevents an
indefinite silent stall, but callers may see a transient failure during detection
and reconnect. Existing durable request recovery still governs interrupted work.

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

### Verified local image archives

The reviewed recovery extension retains one OCI archive for an affected immutable
image under the existing root state `verified-archives/` before removing any
image aliases or unpacked snapshot. It exports original compressed content,
validates every included blob digest and size, binds the top reference to the
admitted digest and requires the complete Linux/amd64 manifest, config and layers.
It never archives the damaged unpacked filesystem. Archives remain root-owned;
validation streams bounded buffers and imposes the existing finite content-size
boundary. This uses disk, not an additional service or resident image cache.

A retained archive also supplies fresh trusted baseline content if native
compressed blobs are missing or damaged, with fresh descriptor checks before use.
Repair reimports this verified archive and rechecks the unpacked files against
the trusted baseline. It does not need to pull the replacement from the original
registry. An unavailable original or invalid archive fails before removal;
uncertain import or failed replacement verification remains operator-required.
Archives are retained for recovery evidence; do not delete an archive while its
image or retained incident still needs it. An archive does not authorize an image
upgrade, foreign repository, caller path, namespace or workload.

If a crash removed image metadata before the one archive import started, the
root checker reports that exact interrupted replacement. Recovery may finish its
single verified import without repeating removal. An already-started uncertain
import is not replayed; fresh byte proof can establish that it finished. Missing
metadata without the matching incident and valid archive remains blocked.

A separate damaged image found while earlier images await consumer readiness
can be repaired under its own existing root incident. The lifecycle preserves
original consumer UIDs, desired replicas, retired-pod evidence and all affected
references. It never repeats completed pod deletion or clears an earlier failed
artifact by noticing a different success. Each image retains its one-attempt
boundary, and final owner readiness is still required before healthy status.

Source checks do not commission this extension. Follow exact merged-source
Security acceptance, `ACTION=install-integrity`, normal activation and native
readback. Current source and reviewed helper/policy hashes must agree.

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

## Optional Repository Metadata Connection

The existing identity producer can explicitly connect one GitHub user or
organization account for metadata readback, including repositories created later.
Follow [Repository Provider Identity](../../../docs/components/operator-orchestration-service/repository-provider-identity.md#account-metadata-reader)
after the exact source and Security acceptance. This grants no content or write
access and does not enable Repository lifecycle mutations.

Its protected delivery receipt selects the connection. This runtime's existing
credential timer maintains it and uses the same OOS group rollout for delivery
changes. An absent selection has no effect; a failed reader does not block the
five required workflow identities or core startup. Optional Secret references
permit restart after revocation. Credential consumption and actual GitHub
health are separate checks. Customer-facing setup remains outside this local
operator procedure's qualification.

Existing-repository linking uses the separate nonsecret
`repository_custody.credential_binding_ref` in the complete-runtime policy. Its
URI identifies `repository-custody-github-app-v1`; its digest comes from the
validated account reader delivery receipt, not the creation credential. Check
the protected receipt against the reader's account contract, Secret and consumed
OOS binding before accepting or changing this reference. Normal activation
projects it as the two server-only `REPOSITORY_CUSTODY_CREDENTIAL_BINDING_*`
values. Omitting it leaves link submission unavailable and preserves lookup and
repository creation. Never substitute the provisioning binding.

The reference records the account/App/installation/metadata scope, not a token
or current connection health. Normal token renewal preserves it; changing the
selected account or installation requires reconciling the reference and accepted
configuration before activation. Revocation and provider failure still deny
owner readback/submission; a configured reference alone proves neither health
nor successful linking. Existing operator confirmation, OOS authorization,
WGCF readiness and canonical custody readback remain required.

## Console capability completion

Epic1332 extends this same lifecycle; it does not create a second runtime or
workflow engine. Its source design is reviewed under Security1342. Final1345
must accept the exact validated Platform candidate tree and merged Console/OOS
sources before Platform merge or commissioning. The three operating stories
remain separate from source completion. Existing model selections, effort,
account custody and six-purpose baseline are preserved.

The final composed Security YAML also selects the existing OOS activation
bundle with `durable_orchestration.manifest_path` and `manifest_digest`.
Its `wgcf_worker_image` additionally binds the exact reviewed worker OCI digest;
source tags alone are not accepted. Status checks the declared digest and
the worker's baked source revision against the reviewed WGCF revision.
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

The fulfiller binding ties the API process to the published caller Secret's
resource version. Resuming base composition therefore reloads restored
credentials even when their bytes match an earlier binding; repeating an
unchanged binding keeps the consuming process. Stored Secret data alone is not
proof of loaded authentication. If live status still reports incomplete
bindings, use the existing normal restart and inspect its owner status; do not
approve a request or relax caller checks to bypass that failure.

Runtime observations use a separate
`governance-console-observations.service` oneshot and
`governance-console-observations.timer`. Periodic collection has its own nonblocking lock,
ten-second per-command timeout, eighty-second service bound and256MiB memory
limit. The timer schedules collection thirty seconds after the prior collection
finishes. Normal activation and restart wait for an existing collector to
release that same private lock, then collect fresh evidence themselves. The
existing lifecycle deadline bounds startup; custody, collection failures and
freshness still fail normally. An overlapping scheduled refresh alone does not
fail startup or require pausing the timer. Its files are private under `private/runtime-observations` in the
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
of `kv/data/components/governed-ai-gateway/dev-integration/codex-account` and
the fixed `kv/data/components/governed-ai-gateway/dev-integration/api-connections/api-*`
prefix. There is no list, delete, undelete or unrelated-secret permission.
Its intended token identity is persisted before issuance, so an interrupted
response reconciles that same identity. Only the gateway receives this token.
The native account is created through Console sign-in; activation never imports
the interactive CLI/Desktop account. The existing credential timer renews the
account lease; unavailable renewal fails visibly and does not widen authority.

A different management token is projected to OOS and the gateway. It authenticates
the fixed OOS/operator pair and grants only the closed model-management API.
Provider tokens are never retained in Console, OOS, source, receipts or process arguments.
For explicitly entered API keys, Console and OOS provide only transient protected
ingress to gateway/Vault; no key is retained in their storage, command journals,
advisor context or receipts. Existing Codex account custody remains separate.
The OOS caller binding is exactly `governance-operations-console` to the admitted
human operator. Its request journal reuses the existing private OOS state mount.

After activation, open Console Model Operations, register an admitted backend,
connect its dedicated account if needed, discover and verify a model, then
review default/task routing, native effort and explicit fallback. The Console
product's [operator procedure](https://github.com/mfshaf7/governance-operations-console/blob/main/docs/product/model-operations-live-integration.md)
owns those controls. Permission/data/output changes still require purpose-profile
review. Public/internal proof does not qualify private client data or stage/prod.

Epic1363 extends this same owner with named **Experimental** Claude API, DeepSeek
API and GLM/Z.AI **Standard API** connections. The label means real-account
qualification is pending and remains after a successful individual model probe.
It is independent of connection health. Fixed HTTPS presets select the native
protocol; callers cannot supply another endpoint. GLM model entry is manual
because this preset has no admitted catalogue API. Unknown native controls use
the explicit provider default. Cloud runtime version/model digest remain unknown
when the provider does not supply them. This does not invent a model inventory.

Adding a connection and storing a key do not prove authentication or model access.
Explicit Verify may consume up to4096 output tokens and60 seconds. Automatic
health performs no API inference; only recent generation-bound successful
verification/requests count as model proof. All seven existing task contracts
retain their original strict final-output validation. Claude's supported native
grammar omits unsupported length constraints, while the full canonical schema
remains in the prompt and is enforced locally. Reasoning content and tool calls
are never projected as task output. Unknown submission outcomes stop routing;
they cannot cause automatic retry or fallback.

Credential replacement invalidates previous model verification. A pending write
is reconciled by its original operation identity against Vault; no second key
write is performed by reconciliation. Explicit Disconnect revokes/fences a key,
including an uncertain earlier write. Reconnect requires fresh credentials.
Before Remove, reassign every route and remove its model registrations. Removal
fences custody and retires the connection identity; routing-history rollback
cannot restore a revoked key or rebind that identity. State and safe receipts
survive restart on the existing owner volume. API connection source may land
before commissioning, but activation still requires the exact composed Security
acceptance and complete-runtime procedure above. Controlled conformance tests
are not proof of any provider account's entitlement or live API reliability.

Restoration also validates every saved backend against current owner admission,
even when the saved settings contain no selected route. A revision referencing
a removed connection is rejected without changing current settings. Its original
historical snapshot remains readable; no metadata or history is silently pruned.
Backend registration and restoration also reuse the retirement lock for every
API connection they reference and re-read current admission inside it. A racing
retirement or registration is reported busy before its effect; explicit retry
then uses current owner state. This prevents an in-flight registration from
recreating a reference while its connection is being retired.

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

Before final readiness, activation re-observes the existing canonical record
owners after frontend preparation, artifact confirmation and provider setup.
Those steps can exceed the five-minute source freshness window on a cold or
slow start. The normal writer must establish fresh authority; a failed refresh
withholds successful startup. Expiry and source validation are not relaxed.

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

The complete-runtime drop-in has a finite45-minute startup budget instead of
inheriting the generic single-profile15-minute budget. Complete startup includes
the integrity helper (independently bounded at600seconds), sequential participant
startup, scoped identities and consumed bindings, the accepted frontend artifact,
final readback and failure compensation. Component deadlines still fail early;
this outer budget is not a promise that unavailable dependencies or hardware
faults can recover. The worker's cold package preparation is separately bounded
and its rollout allows ten minutes. Shared verified package downloads reduce
repeated preparation without trusting cached executable trees.

The owner journal records fixed startup phases without command arguments or
binding values. The composition's live combined output is retained as mode0600
`composition-*.log` under the operator-private complete-runtime
`private/startup-logs/` directory. The journal identifies that private file before
launch; inspect it locally after an interrupted attempt. Do not paste raw output
into chat, source, ART or browser responses. Token/Vault calls outside composition
startup keep their existing in-memory capture; this is not general credential
logging. Interrupted output is diagnostic evidence, never readiness or a result
receipt. Preserve it while troubleshooting; normal status remains the acceptance
check after startup finishes.

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

## Core startup and configured AI providers

Core readiness covers owned services, accepted artifacts, policy, identity,
storage and management APIs. It does not require installed Ollama models,
a connected hosted account or any available model. The managed gateway uses its
existing `/healthz` probe; `/readyz` remains separate capability evidence.

After all core checks and their receipt succeed, a same-boot, exact-decision
signal enables provider metadata checks on the existing observation timer.
The initial startup collection does not probe providers. A provider failure
cannot fail core startup, restart the composition or change routing. Model
Operations shows the resulting expiring observations; absent/invalid evidence
is unknown. Check selected primary and fallback registrations there.

A changed local runtime/digest/native effort requires explicit **Verify & update
registration**. This uses the existing verified model registration and retains
stable route references; it is not automatic trust of new provider bytes.
Dedicated-account presence is reported as connection unprobed. Routine checks do
not launch Codex or infer; explicit verification or a real invocation supplies
its own evidence. Provider software/credentials remain operator choices, while
shipped adapters, authorization and executable integrity stay Platform controls.

### Profile and Governed Releases readback

The Console maintenance extension uses the existing authenticated Platform
provider for `GET /v1/console-operations/governed-products`, brokered by OOS's
separate default-off `OOS_GOVERNED_PRODUCTS_ENABLED` boundary. It reads committed
Workspace Governance product metadata and fixed owner-defined release records.
Only validated committed regular files are read; callers cannot choose host paths.
List reads do not probe runtimes or execute scripts.

After exact composed acceptance, normal `activate` and `restart` bind
`OOS_DEV_INTEGRATION_PROFILES_ENABLED` and `OOS_GOVERNED_PRODUCTS_ENABLED` through
the existing canonical-record binding. Readiness verifies both consumed flags;
rollback disables and removes them. Profile request recording uses the existing
operator binding and private operation state. These flags do not commission the
separate native release App or permit protected owner-workflow dispatch.

The Console retains the existing register and Dashboard. Products without a
release rail remain inspectable. Source, observation time and individual record
timestamps stay distinct. Protected workflow buttons navigate to the existing
GitHub workflow; they do not submit commands or issue Console release receipts.
Navigation alone changes no stage/prod state. The optional native connection below
extends the existing operation provider; it remains disabled until commissioned.

Commission only after exact-source composed review covers the Console, OOS and
Platform changes, including bounded product pages, stale/unavailable owner reads,
caller denial and absence of runtime side effects. Retain existing approvals in
the protected owner workflow. Keep canonical operations/requests during rollback.
See the [OOS operator procedure](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/governed-release-readback.md)
for readback, history continuation and explicit execution limits.

### Optional native governed-release connection

This is a post-setup connection, not an installation or core-startup dependency.
Reuse the current Console → OOS → Platform operation journal/provider and the
three existing protected OpenClaw workflows. Do not install a new executor,
reuse Gary or another workflow App, import personal credentials, approve an
environment automatically, merge a PR automatically, or run local prod scripts.

The default source policy permits this optional adapter but supplies no native
activation grant or credential. Its dedicated definition is `security/governed-release-identity.yaml`:
selected `mfshaf7/platform-engineering` repository id1195328534, dedicated
`mfshaf7-governed-releases` App owned by account id244414185, Metadata/Contents/
Pull requests read and Actions write only, no subscriptions or administration.
Existing protected `stage` and `prod` environment approval rules stay in force.
The workflow's existing token creates its source PR; the dispatch token cannot.

After source review/landing, qualify the exact Console/OOS/Platform/Security
composition with the existing complete-runtime procedure. The fresh composed
Security decision must cover native release authority. Its native review
front matter must name `status: accepted`, the same `gate_id`, exact
`reviewed_revisions` and `reviewed_platform_tree`. The existing resolver derives
`security_accepted` and the decision digest into its existing private provider
policy; never hand-pin that digest into tracked source or invent an alternate
activation policy. Missing/pending native acceptance leaves core activation
independent and native actions unavailable. The source delta
review is [here](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-02-console-native-governed-release.md).

Validate the definition without connecting to GitHub:

```bash
make governance-console-release-identity ACTION=validate
```

Create/install the dedicated App with that exact scope and store only its private
key at Vault `kv/components/governance-operations-console/governed-release-dispatch`,
property `privateKey`. Account consent is a browser action. Do not store keys in
source, browser data, OOS, receipts or command output. Use the existing Platform
Vault endpoint/session. Commission explicitly against the existing materialized provider policy:

```bash
make governance-console-release-identity ACTION=commission \
  ARGS="--policy <existing-materialized-provider-policy> --app-id <dedicated-id> --installation-id <selected-installation-id>"
make governance-console-release-identity ACTION=status \
  ARGS="--policy <existing-materialized-provider-policy>"
```

Commissioning proves the App, account, installation, exact permissions, selected
repository numeric identity, token scope and expiry. Its private atomic600 bundle
lives under the fixed Platform runtime root. Existing credential maintenance
renews it; shared lease/exclusive rotation prevents using a token during its
replacement. Rotation retires the old token before issuing a new one. A provider
or Vault outage withholds native submission and does not block core startup.

Commissioned Console actions use the [OOS procedure](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/governed-release-readback.md#submit-an-owner-release-request).
Retain real dispatch/run/approval/source-review/merge/readback evidence during
controlled qualification. Isolated GitHub fixtures qualify source behavior only;
they do not prove real App installation or stage/prod operating acceptance.

For rollback, revoke the exact current token (the missing lease prevents renewal)
and withdraw native acceptance in the owning Security review when appropriate, and keep existing canonical commands, owner records and
receipts. Revocation failure retains custody for a retry; do not claim revocation
from a failed provider response. A disabled connection does not erase pending
source branches or approve/cancel outstanding GitHub work.

```bash
make governance-console-release-identity ACTION=revoke \
  ARGS="--policy <existing-materialized-provider-policy>"
```

Original dispatch uncertainty is read-only recovery: do not delete its write-ahead
marker, repeat a native run, create a replacement command, or infer completion
from a workflow conclusion. Human review and source merge remain required. A
verified desired-state receipt does not establish observed resource health/UAT.

## Owner release records after a merge

Native source admission distinguishes the accepted running code from current
GitHub owner records. Only the fixed OpenClaw release, verification, lifecycle and
associated desired-state YAML paths declared in `console_release_source.py` may
differ. All other Git leaves must match the accepted Platform source; main must
retain its ancestry, and each read blob must match the verified complete tree.
No local checkout is advanced and no fetched code runs in the provider.

After a normal record-only merge, refresh products and review another action at
the new owner-data revision. No code repin or CLI repair is required. Current
owner main, accepted local snapshot and retained remote snapshot are distinct.
Only current owner main can admit a new native command. A failed connection keeps
a labelled derived snapshot readable; it grants no authority. Original operations
retain their independent exact-read/receipt recovery.

One private snapshot is persisted atomically with an integrity digest. In-memory
head proofs/document caches are bounded to four revisions; unchanged blobs are
reused by immutable identity. The complete Git-tree proof is bounded by the
existing provider's2MB response limit and20,000 entries, with a short refresh
budget. Slow/incomplete reads withhold new actions and can continue warming on
the next refresh. This is a bounded adapter, not unlimited indexed storage.

The workflow-created source PR may show GitHub's **Approve workflows to run**
banner. The human reviewer starts those checks and waits for required results
before merge. The native adapter does not add an approval bypass or substitute
workflow success for source review. See [GitHub's workflow-trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

### Optional automatic profile-request preparation

The single-form Model request extension is source-staged and disabled by default.
After exact composed Security acceptance, the reviewed `purpose_profiles`
policy may set `preparation.enabled: true` and `preparation.context_base_url`
to the accepted CGG service origin. This is internal Platform configuration,
not a user-entered form value or a provider account requirement. The owner
composition binds the corresponding OOS preparation flag and CGG origin.
Existing model-management caller, operator and token custody are reused.

A disabled preparation path does not prevent core startup or native full-reference
requests. Disabling/rolling back clears the preparation flag and origin, retains
canonical request history and leaves CGG artifact custody with CGG. The approved canonical
policy selects preparation, but the adapters default off and commissioning still
requires exact composed acceptance. Do not hand-edit runtime environment files or widen
credentials to make the form appear connected.

## Capability profile commissioning extension

The source-only maintenance extension supports explicit permission-preset
selection inside the existing model configuration and native profile lifecycle.
It needs the same fresh exact-source Security/composition acceptance and a
disposable real profile witness for operating acceptance. The approved canonical
policy selects preparation and lifecycle; adapters still default off and exact
composed acceptance precedes commissioning. Source proof or preview is not
commissioning.
Definitions, effects, limitations and original-request recovery belong in
[Model management](../../../docs/components/governed-ai-gateway/model-management.md#capability-permission-profiles-maintenance-extension).


### Native profile implementation prerequisites and parent context

When native profile lifecycle is selected, the provider's documented operator
tool path must contain Node22, npm, gh and make as well as its existing base
tools. An interactive NVM shell alone does not supply the service PATH. Keep
those installed tools in the existing operator tool directory or standard Unix
paths; do not alter global manager environment or runtime policy to bypass a
missing prerequisite. Startup checks presence before runtime effects.

A gateway policy update inherits its verified active parent composition context
through the existing bounded child runner. It retains the parent's namespace,
consumer and credential bindings. Missing or degraded context stops the original
operation without a standalone fallback. Resume that operation after the parent
is healthy. Original approved policy bytes must remain exact; separately accepted
current executable maintenance may advance without rewriting the original
receipt. Native rollback restores the three policy files and retains that code.
