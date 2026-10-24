# ADR-030: Configurable AI backends, native effort and task routing

## Status

Accepted design for source implementation under Delivery Epic 1313. Composed
Security acceptance and Platform commissioning remain separate work.

## Context

The gateway already owns provider invocation, profile permissions, task/output
contracts and audit. Its source-selected Ollama bindings do not give the
operator live model registration, task choices or explicit fallback. The
Console's next code-authoring work depends on that complete configuration path.

## Decision

Extend the existing gateway. Preserve its six profile identities, CGG context
requirements and consumer output schemas. Profiles authorize callers, tasks and
data; Platform-owned backend policy authorizes protocols and connections.
Within those permissions, model registration and default/task routing are
private revisioned runtime configuration. They require no new ART story or
source PR for each model or effort choice. Permission/protocol expansion keeps
the existing reviewed source lifecycle. OOS owns authenticated operator intent,
workflow state and recovery; the Console owns interaction. An OOS management
credential is permission to use the bounded management API, never a provider
account credential. Provider accounts remain in Platform Vault custody.

Use native Ollama metadata and Codex app-server model/effort discovery. There is
no intelligence ranking, fixed provider preference, API-key substitution or
effort coercion. Registration performs a bounded synthetic inference; catalogue
metadata alone proves neither entitlement nor successful model operation.

Use the supported Codex app-server protocol with a pinned executable, private
HOME/CODEX_HOME and scratch directory, an ephemeral read-only thread, shell and
web tools disabled, and rejection of action requests/tool items. The managed
ChatGPT account signs in separately through native device authorization and is
stored only in a dedicated Vault KV path. Interactive Codex credentials,
plugins, project roots and source credentials are not inherited. This adapter
does not implement interactive code editing or source execution.

Save configuration with expected-revision compare-and-swap, immutable history
and exact command replay receipts in the existing private gateway state volume.
Freeze each invocation's selection and retain its result under original
caller/operator/task/correlation identity. Only pre-submission unavailability
or capacity exhaustion can try the configured fallback order. Policy/schema
denial, integrity failure and unknown completion stop. Restart never reruns an
unresolved original invocation. Business/source acceptance remains with OOS.

## Consequences

Defaults and overrides can change without changing execution code or the
Security-accepted source tree. Source-selected bindings remain the explicit
legacy choice when no runtime selection is configured. Old invocation wires
remain valid; callers negotiate effective selection evidence separately.

One shared local-provider inference slot and one shared Codex process slot
bound concurrency. Managed local calls unload after completion. Codex provides
no native output-token field in the installed app-server contract; the adapter
bounds elapsed time, message queues/bytes and final output bytes instead of
pretending it enforces that setting. Container and egress limits belong to the
composed commissioning candidate. Routine readiness never launches Codex or
infers; management availability and provider availability are separate facts.

The gateway source producer is not complete Console operation. OOS and Console
consumers, Security review of actual composed sources and the commissioning PR
tree, owner deployment, and all-consumer operating proof must follow. The live
change record belongs to commissioning, not this source-only foundation.

## Alternatives Considered

- A separate model gateway, policy engine or storage service: existing owners
  already provide those boundaries; another service would duplicate authority.
- A source/profile lifecycle for every model or effort choice: this confuses
  ordinary configuration with task/data permission changes and creates source
  acceptance churn.
- Ambient interactive Codex authentication or direct provider access from the
  Console: these would cross existing credential and execution boundaries.
- Automatic fallback after a timeout or malformed answer: completion and task
  acceptance would be ambiguous, and duplicate effects could follow.
