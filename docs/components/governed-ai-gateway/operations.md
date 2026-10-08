# Governed AI Gateway Operations

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

- [access.md](access.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
