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
