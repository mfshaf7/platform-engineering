---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime, ai]
  reviewed_artifacts:
    - scripts/model_profile_lifecycle.py
    - scripts/test_model_profile_lifecycle.py
    - scripts/test_ai_task_routing.py
    - dev-integration/profiles/governed-ai-gateway/runtime/model_profile_resolver.py
    - dev-integration/profiles/governed-ai-gateway/runtime/model_configuration.py
    - dev-integration/profiles/governed-ai-gateway/runtime/model_management.py
    - dev-integration/profiles/governed-ai-gateway/runtime/task_routing.py
    - security/schemas/model-profile-source-projection.schema.json
    - dev-integration/profiles/governed-ai-gateway/runtime/profile_request_setup.py
    - dev-integration/profiles/governed-ai-gateway/runtime/gateway_app.py
    - dev-integration/profiles/governed-ai-gateway/scripts/common.sh
    - products/governance-operations-console/scripts/console_model_management.py
    - .github/workflows/build-and-validate.yaml
    - products/governance-operations-console/scripts/test_console_model_profiles.py
    - products/governance-operations-console/scripts/console_model_profiles.py
    - products/governance-operations-console/scripts/platform_operation_provider.py
    - products/governance-operations-console/scripts/console_profile_requests.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/complete-runtime-policy.yaml
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
  notes: Prepared request and bounded native lifecycle adapter; approved canonical selection still requires exact composition acceptance before activation. Policy/source admission, source custody, explicit Security and human review, recovery and runtime readback use the fresh lifecycle assessment. No new service or native-v1 protocol change.
---

# Owner-backed Model profile request setup

## Summary

Remove the normal requester's need to find caller IDs, context hashes and output
schema paths. Platform exposes existing registered workflow contracts as bounded
metadata; OOS consumes them and performs real context admission before using the
existing request/review service. Console supplies a single user-facing form.

## Profile lifecycle scope extension

The operator approved completion of the native profile lifecycle through the
Console, retaining this maintenance batch and its per-owner Landing Units.
Extend the existing OOS request/decision state, Platform operation store, native
lifecycle CLI, Gary maintenance publication and human exact-head merge. The
normal review now records an actual artifact atomically; explicit role-bound
Security acceptance is separate. The Console exposes impact, review, source
handoff, progress, running readback, original recovery and receipt-bound rollback.
The control does not require AI inference or available providers.

The Platform whole-tree acceptance check previously would invalidate itself on
profile changes. The same exact-source admission is extended only for a complete
native receipt/readback chain through the three policy files. Other source and
unreviewed policy still fail closed; no generic source trust bypass is added.
The approved canonical policy selects lifecycle and preparation; adapter defaults
remain off until commissioned. Native original request/command/fulfillment/
receipt/projection schema bytes and the existing source lock remain compatible.
Source/controlled conformance and preview are separate from later commissioned
operating proof. See the
[fresh lifecycle assessment](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-06-model-profile-lifecycle.md).

## Classification

Operator-approved maintenance of the existing Console request workflow, outside
an active ART initiative. No new ART item, improvement candidate, service,
storage subsystem or model authority. Landing Unit decision
`feature_single_landing_unit`, `maintenance-model-profile-request-usability-platform`,
branch `maintenance/model-profile-request-usability`, base
`f9ae516794e0c208858ec546718b96185f27f337`. This source owner has a separate
review/rollout/rollback boundary from OOS and Console.

## Ownership

Platform owns the resolved workflow/caller/output contracts, management API,
commissioning and source activation. OOS owns preparation and native request
state. CGG owns context admission and artifact custody. Console owns the form.
Security acceptance remains independent of request submission and UI preview.

## Root Cause

The old form exposed the native integration payload directly. Reusing historical
requests cannot be a complete current workflow catalog: inspection found matches
for only one of six registered profiles. A cleaner form therefore requires a
current owner lookup, not hidden mandatory fields or invented references.

## Source Changes

The existing management-authenticated listener projects admitted task setup
without private schema contents, provider/account data or model probes. The
hash covers request setup, so provider/model changes do not unnecessarily
invalidate the draft. Tests resolve all six source fixture profiles and seven
tasks. Caller ownership must be recorded by the native workflow identity.

Complete-runtime composition accepts an optional preparation configuration,
validates the CGG origin, binds it only after accepted policy and clears it on
disable. The approved canonical policy selects the existing origin; runtime
activation remains gated by exact composition acceptance. It adds no startup dependency on
provider availability and preserves native full-reference request compatibility.
The pinned native-v1 fulfillment contract remains valid because its request,
command, receipt and fulfillment schemas are unchanged.

## Artifact And Deployment Evidence

Rendered ConfigMap import proof covers the new helper dependency.
Four focused metadata/authentication tests,34 existing model-routing tests and11
profile composition tests pass. Current complete-runtime and owner validation
results accompany the source review. These are source and isolated conformance
witnesses, not real provider, context-service or deployment qualification.
The [fresh source assessment](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-06-model-profile-request-usability.md)
covers caller binding, metadata minimization, CGG custody and activation limits.

## Sequence And Rollback

After operator preview approval, land OOS contracts, this Platform producer and
the Console consumer, then generated Security owner-record evidence and exact
composition acceptance. Commission only that accepted composition.
Rollback selects the prior paired sources or disables preparation; canonical
requests, CGG artifacts and the existing native request path remain intact.
No operating acceptance or complete-workspace-clean claim is made by this record.


## Live Verification

Not deployed or commissioned in this preview turn. Native request/source
qualification follows operator approval, reviewed landing and exact composed
acceptance. Browser samples do not establish operating readiness.

## Follow-Up

Keep the runtime on its prior accepted composition until this batch is accepted.
Regenerate and land Security owner-record evidence after owner merges, qualify
the actual CGG/owner request path, then retire Landing Unit credentials, branches
and worktrees through the existing maintenance process. No new ART is required.


## Lifecycle Validation And Release Boundary

Fourteen controlled adapter tests exercise native source validation, actual
three-document apply/readback/rollback, creation/task configuration, exact
source acceptance, requalified startup, decline, interrupted authoring, writer
exclusion, runtime failure, control-only all-inactive launch and the existing
artifact-recovery guard. Additional native lifecycle, provider, composition,
model-management and complete-runtime suites pass. Owner structure, governance,
operational docs and generated Security evidence are current in the candidate
workspace. GitHub/CI/Kubernetes responses in controlled tests are isolated inputs;
they do not claim a real provider, account entitlement or deployment witness.

The operator approved publishing the reviewed batch. Its canonical policy selects
preparation and lifecycle using the existing context-service origin, existing OOS
loopback access and explicitly admitted operator identity. Exact composed Security
acceptance remains the activation gate. After reviewed source, qualify the exact
commissioned composition with a disposable profile through the Console and
interruption/restart paths. Preserve current working profiles and private evidence.

## Capability profile repair extension

The operator approved several named permission profiles per installed AI
capability and explicit selection. Retain the existing Landing Unit and source
review boundary. Native source validation now crosses the actual runtime resolver;
compatible profile variants inherit unique base caller registrations and stable base
capability identity. Base maintenance keeps shared contract/binding scaffolding
coherent while retaining each variant's policy limits, lifecycle and prior
activation approval. Source projection and runtime eligibility both include
base-capability activation; an active variant cannot bypass a suspended base.

The existing private model configuration journals `profile.assign`. Both base
and selected policy must authorize input; effective limits are their intersection
with provider ceilings. The one captured configuration revision binds policy and
model routing. Source-binding adapters apply the stricter limits without adding
provider concurrency. Original invocation identity survives assignment changes,
process restart and uncertain completion. Data-scope notes document policy; they
do not compile into new access rules or instructions. The existing integration
and CGG retain actual data authority.

Normal creation carries operator-selected limits to the prepared target rather
than losing them as review text. Catalog guides distinguish implemented capability
behavior from review descriptions. Names and operating rules enter source review;
private request context remains in existing custody. OOS owns atomic policy
revision/re-preparation and the native review sequence. Full procedure and exact
limitations are in [Model management](../../components/governed-ai-gateway/model-management.md#capability-permission-profiles-maintenance-extension).
The original preview proof changed no live runtime. Publication selects the
canonical preparation/lifecycle configuration; exact composition acceptance and
an operating witness remain separate. The fresh lifecycle assessment covers it.

Final release inspection corrected the native running-policy observation URL to
the gateway's existing `/readyz` route. The adapter tests now execute their actual
observation script against the real gateway HTTP handler with controlled source
data; the old URL reproduces HTTP404 and the corrected URL supplies the checked
policy readback. This changes no activation authority or endpoint contract.


## Publication readback correction

The real OOS publication receipt reports the source App as
`mfshaf7-agent-gary[bot]`; GitHub's `gh pr view` reports the same App as
`app/mfshaf7-agent-gary`. The lifecycle adapter must accept the exact publisher
identity as well as its existing GitHub display label. No other author gains
permission. The later repository/head/base and exact human-review checks stay
unchanged. The existing native adapter harness now returns the actual publisher
receipt's author field instead of omitting it, exposing the mismatch before the
one-line correction. All native adapter cases must then pass.

This required publication repair is owner-repo maintenance under the approved
batch. Landing Unit decision `child_isolated_landing_unit`,
`maintenance-profile-publisher-readback-platform`, branch
`maintenance/profile-publisher-readback`, base
`a6d6a1f8e053fcec989ed66c7e0849aa1340ff36`. It is a separate source landing because
the preceding source review has already merged; no ART item or new mechanism.
Exact composed Security acceptance must advance to the new merged tree before
commissioning. The earlier source assessment's identity boundary is preserved.

The primary operator runbook now also reflects the approved canonical flag
selection; it no longer says those source flags remain off. Runtime acceptance
and the actual operating witness remain separate.


## Composition-preserving runtime reconciliation

The real Console request reached approved source, Gary publication and human
merge (PR372). Running apply correctly failed the existing ownership guard:
its gateway is part of the accepted runtime composition, while the new adapter
had invoked a standalone profile update. The guard is unchanged. Reuse the
existing validated active-composition lookup and bounded child environment for
this finite gateway action, retaining original namespaces, dependencies and
credential bindings. Missing, incomplete or degraded parent context cannot fall
back to standalone mutation. Credential values pass as process environment,
never command arguments, browser data or logs.

Execute current clean, independently accepted Platform code only after its three
policy documents match the original merged receipt. This permits a separately
reviewed maintenance landing to advance executable acceptance while original
request/source/rollback evidence remains unchanged. Unaccepted code, unrelated
policy drift and corrupt receipt chains still deny reconciliation. Rollback
continues to restore only the original three policy documents and preserves
later independently accepted executable maintenance.

The service also lacked Node/npm in its documented tool path, although the
terminal's NVM installation worked. The existing admitted Node22/npm installation
is now persistently linked into the operator tool directory. Native lifecycle
selection adds Node/npm/gh/make to the existing controlled-path startup preflight;
unselected lifecycle does not make those optional management tools a core gate.

Landing Unit decision `child_isolated_landing_unit`,
`maintenance-profile-composition-reconcile-platform`, branch
`maintenance/profile-composition-reconcile`, base
`63e825845a3e3d6d5b6acf3e0d84b0498428d6a7`. This owner maintenance repair changes no
ART item, service, browser-selected path, profile policy or composition guard.
The existing adapter harness now calls the actual ownership guard; it fails the
old standalone invocation, rather than assuming runner success. Current accepted
code plus unchanged policy, inactive context, original recovery and receipt
restoration remain explicit tests. Exact composed Security acceptance, deployment
and the original actual Console operation/rollback remain required.
