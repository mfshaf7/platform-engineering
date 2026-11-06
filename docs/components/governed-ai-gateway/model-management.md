# Model management and workflow AI configuration

This is the Platform operator/API surface for the configurable AI foundation.
The source producer is implemented under Delivery 1316. It becomes an operating
Console workflow only after OOS 1317, Console 1318, Security 1319 and Platform
1320 commissioning, followed by operating qualification 1321. Do not enable
unreviewed source or substitute handcrafted files for the completed Console flow.

## Ownership and runtime selection

Existing profiles retain caller, task, CGG data and output-schema permissions.
The accepted Platform runtime supplies fixed backend connections and allowed
tasks. Registering a model, choosing native effort, changing defaults/overrides
and rolling configuration back are owner configuration operations within those
permissions. Expanding protocols, endpoints or task/data authority remains a
reviewed policy change. Model output never grants source or mutation authority.

The original profile bindings and their local-only source notes continue to
describe the legacy source-selected route. Epic 1313 separately reviews the
managed backend policy for the same existing caller/data/task/output scopes;
that exact composed acceptance is required for any alternative provider or
model. It does not activate the pending direct OpenAI API route or qualify
private-client data. The commissioning source, account lease and rollback
procedure extend [the complete Console runtime](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).

`GOVERNED_AI_MODEL_MANAGEMENT_POLICY_PATH` selects the accepted non-secret owner
policy. With no selected policy, legacy invocation behavior remains and the
management routes report `model-management-not-commissioned`. Never select a
policy merely to bypass commissioning. The existing owner runner must bind the
exact accepted source/image, policy, credential projection and network controls.

The closed policy contains `schema_version: 1`, `caller_id`, `operator_id`,
`token_file` and `backends`. Each backend has `allowed_tasks` expressed as
`<profile-id>/<task-kind>` and one implemented protocol:

- `provider: ollama`, with fixed `endpoint_origin`.
- `provider: codex-app-server`, with fixed `executable`, raw SHA256
  `executable_digest` and `vault: {address, mount, path, token_file}`.

The management token authenticates the bounded OOS management caller. It is
separate from the native account and from the purpose-limited Vault token.
The dedicated Vault token permits only the selected account path; it is not a
Vault root token or an OOS/browser credential. Credentials are private files,
never `NEXT_PUBLIC_*`, arguments, API bodies, receipts or source.

## Normal operator flow

Use the Console Model Operations controls after composed commissioning:

1. Register an admitted backend. If it is Codex, start its dedicated managed
   account sign-in, open the returned native verification URL and enter the
   one-time code. Observe the original login request until it is connected,
   cancelled, failed or interrupted. Replaying start never creates another
   login. A restarted unfinished native login requires an explicit new request;
   matching Vault provenance can reconcile an already committed login.
2. Read the actual backend model catalogue and selected model's native effort
   metadata. Local catalogue listings may have `supported_efforts: null` until
   the selected model detail is read. This means unknown, not unsupported.
3. Register the exact advertised model. Platform performs a bounded synthetic
   schema-constrained inference and records its real verification reference.
   Catalogue presence alone is not verification or ongoing availability.
4. Choose a default and optional task overrides, native effort, and up to four
   ordered eligible fallbacks. The final disposition is `fail-closed` if none
   succeeds. The interface must not rank models or silently translate effort.
5. Save against the observed revision. Resolve a conflict by reading current
   state and reviewing a fresh command. An original command can be replayed
   verbatim after response loss; changing its content or actor is rejected.
6. Inspect the effective selection on actual workflow calls. Changing settings
   does not retroactively change a running or unresolved invocation.
7. Roll back by selecting a retained configuration revision and saving a new
   revision. Current permissions are checked again; history cannot restore
   revoked authority. Configuration rollback does not replace source rollback.

A null default preserves source-selected bindings. An absent override inherits
the default; an explicit null override selects that task's source binding.
Effort values preserve their native JSON type. Codex advertises strings; Ollama
may advertise booleans or model-defined strings. Missing Ollama thinking
metadata permits only the model-default null choice. Private reasoning is never
returned or logged; only the canonical task answer can leave the adapter.

## Owner API

These routes use the existing gateway listener. They require `Authorization:
Bearer <management-token>`, `X-Platform-Caller` and `X-Platform-Operator` matching
the accepted policy. OOS constructs those values server-side. There is no
provider endpoint, account token or caller-selected authority in request input.

| Method | Route | Result |
| --- | --- | --- |
| GET | `/v1/model-management/backends` | Admitted backend IDs, task eligibility and registration state; no credential paths |
| GET | `/v1/model-management/configuration` | Current revision, digest and configuration |
| GET | `/v1/model-management/configuration?revision=<n>` | Retained configuration for reviewed rollback |
| GET | `/v1/model-management/catalogue?backend_id=<id>` | Native model catalogue |
| GET | `/v1/model-management/catalogue?backend_id=<id>&model=<model>` | Selected model/effort detail |
| POST | `/v1/model-management/commands` | Original owner acknowledgement/receipt |
| GET | `/v1/model-management/account-login?command_id=<id>` | Original operator-owned login status |

Every command contains exactly `command_id`, integer `expected_revision`,
`action` and `input`. Configuration actions return the original command digest,
actor, previous/new revisions, configuration digest and receipt digest.

| Action | Exact input |
| --- | --- |
| `backend.register` | `{backend_id}` |
| `backend.remove` | `{backend_id}`; remove its unused models first |
| `model.register` | `{backend_id, model}` |
| `model.remove` | `{model_id}` |
| `routing.save` | `{default, overrides}` |
| `routing.rollback` | `{revision}` |
| `account.login.start` | `{backend_id}` |
| `account.login.cancel` | `{login_command_id}` |

The model registration key is the canonical SHA256 of `{backend_id, model}`;
read it from current configuration, rather than asking the operator to hash it.
A route has exactly `primary`, `fallbacks` and `on_exhausted: fail-closed`.
Each primary/fallback contains exactly `model_id` and `effort`. Override keys
must be real current profile/task pairs. Every selected model must be verified
and its backend admitted for the task/data boundary.

## Invocation, evidence and recovery

The existing `/v1/governed-ai/invoke` profile/task/input/output contract remains.
New consumers request `selection_evidence_version: 1` to receive
`effective_selection`: revision, configuration digest, task, ordered attempts,
actual backend/model/native effort and selection reference. Audit contains the
same evidence. `binding_selection_ref` remains the reviewed source-policy
binding; it does not substitute for effective runtime selection.

Policy/context denial happens before routing. Only known pre-submission
unavailability or provider capacity exhaustion permits configured fallback.
Invalid output, changed model identity/effort, timeout or unknown completion
never triggers it. An unresolved original invocation reports
`provider-completion-unknown`; preserve its identity and reconcile through OOS.
Never change correlation identity merely to turn an uncertain result into an
automatic retry. Consumer approval and source acceptance remain independent.

Private configuration/history/command receipts and individual invocation files
live on the existing gateway state volume. Atomic replacement, filesystem locks
and persisted original identities survive process restart. Do not delete state
to repair a conflict. Sign-in restart reads only matching native owner Vault
provenance; it does not adopt the interactive Codex session.

With management commissioned, `/readyz` separately reports management API
availability. Its source-binding provider checks retain their existing meaning.
Management stays reachable for sign-in or repair when providers are unavailable.
Neither API readiness nor a historical registration proves current entitlement
or actual workflow completion. Routine readiness never starts Codex or infers.

## Bounds and commissioning evidence

Managed Ollama calls share one local-provider slot and use `keep_alive: 0`,
which [unloads after the call](https://docs.ollama.com/api/chat). Native thinking
choices come from [model metadata](https://docs.ollama.com/capabilities/thinking)
and are revalidated immediately before use. No unsupported name can silently
fall back to the provider default.

Codex metadata, login and inference share one native process slot. The pinned
app-server uses an isolated account projection and scratch directory, with no
project roots or ambient environment. It rejects tool/action requests and
unrelated thread/turn completion. Native output-token control is unavailable in
the installed protocol; elapsed time, bounded queues/messages and final output
bytes are enforced instead. The commissioning candidate must provide the actual
pinned binary/image, purpose-limited Vault projection, egress and container
resource limits. Source merge alone does not approve or deploy that candidate.

Source validation: `python3 scripts/test_ai_task_routing.py` and the admitted
`python3 scripts/test_dev_integration.py` entrypoint. Tests exercise synthetic
providers, real local HTTP/subprocess transport and filesystem recovery. They
are not Codex/Ollama account entitlement or Console operating proof.

## Profile request setup metadata

The existing authenticated management listener also supports
`GET /v1/model-management/profile-request-options`. It returns bounded setup for
registered task IDs: readable workflow label, responsible repository, caller
bindings, environment, output contract and its actual schema digest, default
operating requirements and a digest of those request-relevant coordinates.
It returns no provider credentials, private schema contents or native account
state and never probes or invokes a model. Unknown caller ownership fails closed
rather than inferring an unrecorded repository.

OOS uses this read for its optional single-form profile request preparation.
The setup digest changes with caller/environment/output-contract setup, rather
than unrelated model or provider selection. OOS rechecks it before recording the
request. Context admission, request review and activation remain with their
existing owners. Existing full-reference native-v1 requests and Platform's
pinned fulfillment source reader remain unchanged.


## Purpose-profile lifecycle controls

The Console profile dashboard and request history consume the existing
[OOS operator workflow](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/model-profile-request-operator-surface.md).
Platform's existing authenticated operation provider exposes only profile
prepare, inspect and control. Source preparation reads this owner's registry,
access plane and task contracts without contacting an AI provider. It validates
all three candidate policy documents before returning impact. Policy edits are
bounded data-scope rules and existing runtime limits; changing integrations,
output contracts, provider endpoints or privilege vocabulary remains owner
integration work, never arbitrary browser policy JSON.

The native lifecycle CLI remains the apply/readback/restore authority. The
adapter stores its original request, candidate, actual review artifact,
Security acceptance where required, source PR/head, receipt and rollback bundle
under the existing private operation store. Gary uses the normal maintenance
source identity and OOS publication bridge. The accountable human performs the
explicit exact-head review/merge. The existing runner applies merged state and
actual readiness source digests/profile state prove running truth. Applied source
is separate from available provider service.

A narrow source-admission extension prevents a reviewed policy update from
invalidating its own recovery control. It accepts only an unbroken native
receipt/readback chain from the accepted Platform tree through the same three
policy documents. It verifies saved review evidence, candidate/source hashes,
activation/exception Security evidence, and exact Git source bytes. Missing or
corrupt evidence, unrelated source, unreviewed policy or drift fail closed.
Code acceptance is unchanged. Ordinary complete-runtime acceptance can advance
the anchor after validating this same chain; this is not a generic descendant
or GitHub-main trust bypass.

`purpose_profiles.lifecycle.enabled` is false in checked-in composition. Exact
commissioning needs accepted preparation, the installation's existing OOS
origin and an explicit list of Security operator identities. Bind these through
`console_profile_requests.py`, never browser credentials or copied CLI tokens.
No installer, model/provider startup dependency, new service or database is
introduced. Source tests and disconnected preview do not substitute for a live
disposable-profile witness after accepted source landing.

## Capability permission profiles maintenance extension

The operator approved several named permission profiles per installed AI
capability, with explicit selection. Reuse the existing model configuration
revision, original-command journal, receipt and rollback controls. `profile.assign`
accepts only `{capability_id, profile_id}`; the owner permits only an active,
compatible profile under an active base capability. It cannot add callers,
change prompts, supply endpoints or grant broader implementation privileges.
Legacy configurations without `profile_assignments` retain the base profile.
A retained revision restores its saved choices as a new revision, subject to
current registered capability compatibility; an inactive choice never permits
an inference. Current readback reconciles catalog choices with configuration.

Capability contracts remain stable across variants. Source creation retains a
canonical capability ID and human profile name. Compatible variants inherit the
unique base caller registration; they create no new caller grants. Runtime
resolution rejects duplicate caller IDs. Native source validation includes the actual runtime
resolver. Base-contract/source-binding maintenance updates its variants' shared
scaffolding while preserving each variant's own limits, lifecycle and prior
activation permission; it cannot create a new Security acceptance.

The gateway checks both base and chosen permission policy. The stricter numeric
limits apply, with existing provider caps and conservative no-retry behavior.
Data-scope prose documents approved handling; it does not compile into an access
filter. Actual context access stays with the registered integration and CGG.
A single configuration snapshot binds policy and model routing. Evidence adds
optional `policy_profile_id` while retaining the stable capability/task contract;
original invocation identity remains stable through selection changes and process
restart. Capability usage guides describe implemented input/output and instructions.
Profile descriptions and reviewer notes remain request metadata. Unsupported
provider limits are explained rather than offered as effective controls.

Policy revisions reuse their original request. The preparation adapter reads
current source and admits supporting context before atomically saving a revised
candidate. Prior Security acceptance clears. A replay recovers the original
revision without another owner preparation or context admission. Direct review
metadata edits cannot silently remove prepared integration evidence. New capability
code remains a source-maintainer responsibility; a request is not an implementation.
This extension is staged source/preview work, pending the fresh lifecycle Security
assessment and exact operating acceptance. It adds no service, database or ART.
