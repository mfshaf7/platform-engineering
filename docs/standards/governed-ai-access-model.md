# Governed AI Access Model

## Purpose

Define the shared platform model for governed AI usage.

This standard exists so the workspace can distinguish:

- raw model access
- AI-integrated systems
- AI-governed systems
- explicit AI exceptions

without depending on bare upstream model names or repo-local conventions.

## Core Rule

A model invocation is governed only when both are true:

1. it uses an approved model profile recorded in
   `security/governed-ai-model-profiles.yaml`
2. it reaches the model through the governed AI access plane rather than direct
   provider access

A raw model name such as `gpt-*` or any other provider identifier is not enough
to claim governed status.

## Platform Ownership

`platform-engineering` owns:

- the future internal AI gateway or equivalent governed invocation path
- the approved model-profile registry
- platform-side audit and policy expectations for governed AI calls
- the rollout and lifecycle contract for the access plane itself

`security-architecture` owns:

- the cross-cutting AI governance standard
- trust-boundary review for new AI purposes, providers, and action paths

Owner repos such as `workspace-governance` may consume approved profiles, but
they must not invent repo-local governed-model policy.

## Required Profile Fields

Every approved governed profile must define at least:

- `profile_id`
- `status`
- `purpose`
- `invocation_path`
- `provider`
- `upstream_model`
- `allowed_callers`
- `allowed_data_scope`
- `output_schema_ref`
- `human_approval_required`
- `direct_provider_access_allowed`
- `security_review_ref`

## Profile Status Meanings

- `active`
  - approved for real governed use
- `suspended`
  - reviewable and reserved, but not currently allowed for live governed use
- `retired`
  - no longer allowed
- `exception`
  - explicit non-standard path that must remain separately reviewable

## Allowed Lanes

### Governed Product Lane

- product workloads use only approved active profiles
- direct provider egress from the governed workload should be blocked
- provider credentials live only in the governed access plane

### Governed Operator-Assist Lane

- bounded purposes such as workspace intake assistance may use approved active
  profiles
- operator approval remains required for governance decisions
- suggestion outputs must be structured and auditable

### Exception Lane

- temporary operator or break-glass use that is not yet behind the governed
  access plane
- must not be mislabeled as governed
- should remain explicit, attributable, and time-bounded where possible

## Intake-Specific Rule

`workspace-governance` may record `decision_source: ai-suggested` intake entries
only when all of these are true:

- the referenced model profile is `active`
- the profile purpose is `workspace-intake-assist`
- the profile keeps `human_approval_required: true`
- the suggestion output matches the intake AI suggestion schema owned by
  `workspace-governance`
- the operator acceptance metadata is recorded with the intake entry

## Runtime-Assist Activation Contract

Bounded AI runtime assists must satisfy
`security/governed-ai-runtime-assist-contract.yaml` before any live activation.
The model-profile registry is necessary, but it is not sufficient by itself.

Live activation requires:

- an `active` approved profile with a selected upstream model
- a governed invocation path owned by the platform access plane
- caller identity at the access-plane boundary
- separate operator acceptance identity when human approval is required
- minimum audit fields emitted and retained
- direct provider egress blocked from governed consumers
- a current security delta review for the activation scope
- rollback controls that can suspend the profile or consumer when evidence
  fails

Consumer repos must reference the platform contract instead of cloning AI
policy locally. `workspace-governance`, product repos, and operator workflows
may consume approved profiles, but they do not own profile lifecycle,
provider-secret placement, direct-provider egress decisions, or the access-plane
audit boundary.

Until every activation gate is proven, a runtime assist may be designed,
reviewed, or tested as an exception/non-governed path, but it must not be
recorded as a governed live runtime path.

## Access-Plane Source Contract

The platform access-plane source of truth is
`security/governed-ai-access-plane.yaml`. It defines:

- the shared `governed-ai-gateway` invocation boundary
- allowed profiles and callers
- caller identity fields that must reach the access plane
- provider credential custody and Vault placement rules
- audit fields required at the access-plane boundary
- default-deny admission policy for governed model calls
- the activation state for profile use

The access-plane contract is source truth, not proof of live operation by
itself. A profile remains unavailable for governed live use while
`activation_state.profile_activation_allowed` is false.

## Devint Egress Enforcement

The dev-integration egress source contract is
`security/governed-ai-devint-egress-policy.yaml`. It defines the minimum
devint posture for the first central governance consumer:

- consumer egress defaults to deny
- governed AI consumers may reach only DNS and the `governed-ai-gateway`
  service for AI invocation
- direct provider egress remains denied from consumer pods
- provider destinations such as direct API endpoints are explicitly listed as
  denied
- activation evidence must prove both positive gateway reachability and
  negative direct-provider reachability

If the devint runtime cannot enforce these controls, the caller may still be
tested as a non-governed exception path, but it must not activate the governed
profile or record itself as a governed runtime assist.

## Anti-Patterns

- putting raw provider API keys into product or operator-assist repos
- treating a bare model name as a governance decision
- letting the model mutate active repo, product, or component contracts directly
- silently routing new AI usage through an operator exception path and calling it
  governed later
