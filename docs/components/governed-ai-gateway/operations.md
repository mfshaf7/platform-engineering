# Governed AI Gateway Operations

## Work Design reasoning allowance

Context and Build Tree share the existing Work Design task profile. Its provider
deadline is ten minutes; consumer transport deadlines must include projection,
provider cleanup and response-delivery margin. Reads and unrelated tasks retain
their own limits. Select native `xhigh` separately for the two task overrides
through Model Operations after exact source acceptance and commissioning; this
source update does not change unrelated routing or register another model.

A request that loses its response after submission remains unconfirmed. Do not
automatically repeat it or fall back. Browser cancellation stops waiting and
prevents local edits; it is not evidence that the provider turn was interrupted.
The existing owner deadline still bounds that work. Busy account capacity is
reported separately from provider offline state. Large context must fit the
selected provider; do not increase local model memory or silently shorten input.
Input-capacity refusal is terminal and non-retryable. Only the existing
provider-unavailable/busy outcomes permit pre-submission fallback. Choosing a
suitable model or smaller complete input is an explicit operator action.

This is staged maintenance. Qualify detailed Context and Build Tree requests,
including their rendered results, on the accepted composed source before claiming
the new allowance operates end to end.

## Native advisor draft replies — approved preview batch

Work Design and Agent Console provider outputs now require the closed native
`draft_reply` shape from `security/schemas/advisor-draft-reply.schema.json`.
Each existing profile schema embeds the same shape; tests prove agreement with
the actual strict output validator. OOS validates its semantic intent and scoped
fields, then retains the existing client envelope. Text is a human-readable
summary, not a container for model-authored edit JSON. Normal chat has no edits.

This does not change selected models, effort, permissions, provider tools or
approval authority. Pair the reviewed Platform contract with its OOS decoder and
Console consumer before normal exact-source commissioning. This preview batch
does not claim a live source update or provider qualification yet.

The Agent Console contract also covers the existing Proposal, Prototype
promotion, Execution, blocker-justification and Orchestration draft advisors.
Their role-scoped fields remain OOS/Console input, rather than separate provider
formats. Provider-schema tests reject a legacy edit envelope hidden in `text`
when the required native reply is missing or malformed, for both Agent Console
and Work Design. Ordinary answers carry an empty edit list.

## Prototype source authoring preparation

`prototype-source-authoring-v1` reuses the existing local `qwen3:8b` binding,
route, limits and bounded change-set schema. It is a separate desired-source profile
for the exact `operator-orchestration-service/prototype-source-authoring`
caller and `oos.prototype.source-authoring.v1` task. The profile boundary keeps
Delivery and Prototype task allowlists separate without widening gateway policy.
Its baseline Security reference is an architectural anchor only; this new
purpose requires fresh exact composed acceptance and explicit gateway
commissioning through the Console complete-runtime runbook. The proposed active
source selection is not live authority: keep Platform primary/running gateway
unchanged until that decision. No provider, model or running runtime was added.
Normal later model-profile lifecycle changes use the reviewed path below.
Do not activate it by merely enabling a consumer environment flag. OOS owns
canonical Prototype eligibility, receipt-bound CGG context, app/design scope and
exact-draft acceptance; the model cannot mutate Studio controls or source.

## Model-Profile Lifecycle

Use this source-backed path for reviewed `create`, `amend`, `activate`,
`suspend`, `retire`, or `exception` requests. This extends the existing
registry and access-plane contracts; it is not a separate control plane.

Authority is split deliberately:

- OOS owns request, review, exact revision, and fulfillment workflow state.
- Platform owns the registry, provider/model selection, access plane, source
  application, projection, readback, and rollback.
- Security owns acceptance for `activate` and `exception`.
- The Console may submit intent and render projections; it never mutates
  Platform source.

The normal sequence is:

1. In OOS, record the approved request as `implementing` with actor
   `platform-engineering/model-profile-lifecycle`, then export the current
   request projection. Do not apply a `not-started`, rejected, stale, or
   already-applied projection.
2. Create a Platform decision conforming to
   `security/schemas/model-profile-lifecycle-decision.schema.json`. Bind the
   exact request revision and receipt digest plus the current three-source
   projection. Platform supplies the complete target profile; OOS request data
   does not select a provider or model.
3. Apply in a review branch, capture the receipt and rollback bundle, and land
   the source through normal review:

   ```bash
   make model-profile-lifecycle ACTION=project ARGS="--source-version <base-commit> --output /tmp/profile-source.json"
   make model-profile-lifecycle ACTION=apply ARGS="--request-projection /tmp/oos-request.json --decision /tmp/platform-decision.json --receipt /tmp/platform-receipt.json --rollback-bundle /tmp/platform-rollback.json"
   python3 scripts/validate_ai_model_profiles.py
   ```

4. From clean merged Platform `main`, prove exact source readback and generate
   the OOS `applied` fulfillment payload:

   ```bash
   make model-profile-lifecycle ACTION=readback ARGS="--receipt /tmp/platform-receipt.json --source-version <merged-commit> --review-uri <review-uri> --review-digest <sha256> --recorded-at <rfc3339> --output /tmp/platform-readback.json"
   ```

   Submit only `oos_fulfillment` from that readback to OOS. OOS then owns the
   final workflow transition and its receipt chain.

`create` and `amend` always land as `suspended`; activation is a separate,
Security-bound request. `activate` requires an exact Security decision and a
target that already passes every registry, caller, route, model, audit, and
access-plane validator. A request cannot add an unreviewed provider route or
model. `suspend` and `retire` close activation in the same source transaction.

Retirement keeps the canonical registry row, selected binding and task/caller
history, but removes its access-plane, route and caller grants and retires every
binding. Resolved history is ineligible for invocation; it must not be granted
access merely to make resolution pass. The launcher requires at least one
eligible profile, not an active legacy intake profile. Other active profiles
remain independently usable when intake or Work Design is suspended or retired;
an all-inactive registry cannot launch. The intake/Work Design `smoke` remains a
route-specific inference exercise requiring those two profiles active, not a
generic readiness check or a reason to reactivate a deliberately disabled route.

Behavior unit tests use explicitly synthetic frozen fixtures under
`scripts/fixtures/governed-ai/`; runtime sources never load them. Native source
validation and rendered-registry conformance instead check the actual declared
configuration, without requiring today's profile IDs or active states forever.

If validation or post-apply review fails, restore only from the exact receipt
and rollback bundle while the source still matches the applied result:

```bash
make model-profile-lifecycle ACTION=restore ARGS="--receipt /tmp/platform-receipt.json --rollback-bundle /tmp/platform-rollback.json --recorded-at <rfc3339> --output /tmp/platform-restore.json"
```

The adapter denies malformed OOS contracts, false receipts, stale source or
revision bindings, wrong actors, out-of-order timestamps, repeated input bound
to changed source, incomplete target profiles, prohibited activation, dirty
merged readback, and rollback against drifted source.

After the Console connection and Security decision land, the Feature-level
commissioning sequence writes one short-lived operator-private proof conforming
to `security/schemas/model-profile-operating-proof.schema.json`. The evidence
contains no secrets. It points to the active private OOS caller-secret file,
the live OOS and Console readback URLs, exact Platform artifacts, source
revisions, negative outcomes, and cleanup results.

The ART evidence path runs only the read-only verifier:

```bash
OOS_DELIVERY_ART_EVIDENCE_EXECUTION=true \
OOS_DELIVERY_ART_EVIDENCE_MODE=verification-only \
MODEL_PROFILE_LIFECYCLE_OPERATING_EVIDENCE=/absolute/private/operating-proof.json \
make model-profile-lifecycle ACTION=verify-operating
```

The verifier refuses ordinary interactive execution, non-loopback URLs,
non-private evidence or secret files, expired evidence, changed owner-repo
revisions, false artifact digests, incomplete OOS fulfillment, stale Console
reconciliation, or incomplete rollback and cleanup. It performs no
commissioning, deployment, restart, lifecycle mutation, or cleanup itself.

## Primary Checks

Use the shared dev-integration runner:

```bash
make devint-status PROFILE=governed-ai-gateway
make devint-smoke PROFILE=governed-ai-gateway
```

Smoke is read-only. It proves:

- gateway API readiness
- caller identity reaches the access plane
- audit ledger event emission
- active binding, Ollama version, and model digest match the registry
- intake and Work Design provider outputs pass their strict schemas
- the complete profile registry resolves with independent lifecycle state
- mismatched Work Design caller, profile, and task requests are denied before provider access
- suspending Work Design leaves intake independently available
- consumer can reach the gateway service
- consumer cannot reach the direct-provider sentinel service
- consumer cannot reach host Ollama directly

## Common Failure Signals

- profile is not `active` in the workspace registry
- gateway Deployment is not ready
- consumer probe cannot reach the gateway
- latest audit event is missing caller identity
- Ollama version or model digest differs from the approved binding
- provider response contains malformed JSON, extra fields, thinking, or tools
- provider request times out or the concurrency bound is exhausted
- caller, task contract, version, or output schema does not match the selected
  profile
- direct-provider sentinel is reachable from the consumer probe

## First Response

1. Run `make devint-status PROFILE=governed-ai-gateway`.
2. If the profile is not active, fix workspace registry admission before
   launching runtime.
3. If runtime is active but smoke fails, inspect the generated manifest under
   `.dev-integration/governed-ai-gateway/<operator>/rendered/`.
4. If the sentinel or Ollama is directly reachable, treat the egress policy as broken
   and do not activate any governed consumer.

## Recovery Sequence

Use suspend/resume first:

```bash
make devint-down PROFILE=governed-ai-gateway
make devint-up PROFILE=governed-ai-gateway
```

Use reset only when intentionally destroying local dev-integration state:

```bash
make devint-reset PROFILE=governed-ai-gateway
make devint-up PROFILE=governed-ai-gateway
```

## Evidence To Capture

- `profile-status.txt`
- `model-binding-selection.json` for the intake compatibility projection
- `model-profile-selections.json` for the complete resolved registry
- `smoke-summary.json`
- rendered runtime manifest path
- audit event digest from `/v1/audit/events/latest`
- profile lifecycle state from workspace registry
- exact OOS request revision and receipt digest
- Platform lifecycle decision, receipt, merged readback, and rollback bundle

The smoke summary carries separate intake and Work Design invocation, denial,
selected-binding, caller, task, packet-reference, and schema evidence. The PVC
ledger must retain prior events across an ordinary gateway restart; reset is not
valid persistence evidence because it intentionally destroys local state.

## Related Procedures

The approved unpublished advisor repair pairs native output enforcement with
source-owned OOS work guides and actual Console workflow evidence. CGG/OOS deny
shortened editable context before inference. These remain existing task
instructions and admission paths; model/effort selection, caller credentials,
permissions and explicit operator acceptance are unchanged. Land CGG completeness
and Platform output dependencies before OOS/Console consumers, obtain fresh
composed Security acceptance, and activate the reviewed complete source through
the existing procedure. Passing schema/context tests alone does not qualify
the advisor's real workflow judgment.

- [access.md](access.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
