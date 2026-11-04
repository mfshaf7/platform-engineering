---
security_evidence:
  review_areas: [identity, secrets, delivery, runtime]
  reviewed_artifacts:
    - scripts/agent_source_instance.py
    - scripts/agent_source_identity.py
    - scripts/agent_source_bootstrap.py
    - scripts/agent_source_intent.py
    - products/governance-operations-console/scripts/console_instance_source.py
    - products/governance-operations-console/scripts/console_private_source.py
    - products/governance-operations-console/scripts/console_private_checkout.py
    - products/governance-operations-console/scripts/console_instance_records.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/platform_operation_provider.py
    - products/governance-operations-console/scripts/console_record_authority.py
    - products/governance-operations-console/complete-runtime-policy.yaml
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Private source registration — unpublished maintenance

## Summary

Prepare the existing source issuer to consume installation-private repository
registration. Current Git-backed admission remains the legacy path; native
records keep their actual authority, version and policy.

## Classification

Operator-approved private-repository maintenance outside ART. Landing Unit
decision `feature_single_landing_unit`, `maintenance-private-source-platform`.
This is unpublished source preparation, not operating acceptance or deployment.
Gary author preparation is recorded and its temporary credential revoked.

## Ownership

Governance owns eligibility policy, WGCF stores accepted installation records,
OOS owns the operator request, Platform owns independent authority reads and
source credentials, and Security owns exact-composition acceptance. Project
source stays in its selected repository.

## Root Cause

The existing issuer and host readers derive admission from public Governance
Git records. Private project registration cannot use that storage boundary.
Successful custody or a caller-supplied record digest is not sufficient source
authority. Nor can internal records be represented as fake Git inventory bytes.

## Source Changes

The shared issuer now accepts a distinct internal source snapshot from a
trusted Platform reader. It revalidates installation, owner key, exact record
reference, policy, provider identity and operation eligibility before deriving
the one-repository contract. Proposed registration remains setup-only; ordinary
source requires active Inventory. Setup binds its actual approved finite plan.
The native receipt reference identifies internal authority without a fictitious
Git revision. Current native admission is checked again before token issuance.

The product transport reads only the existing WGCF owner eligibility endpoint
using a distinct read-only Platform binding. It accepts no caller URL, limits
response bytes, rejects redirects and malformed/duplicate JSON, and validates
the configured installation and current accepted policy before returning a
snapshot. Only a positive matching legacy proof selects the Git reader.
Unavailable native state cannot select another authority.

The existing protected provider now exposes finite control-file inspection,
outside generic command journals and model capabilities. It verifies the full
Source App installation before reducing its token to Metadata/Contents read
for exactly one repository. It verifies current commit/tree/blob identity,
regular file modes, byte/UTF-8 bounds and unchanged canonical registration.
The token is revoked before successful response delivery; a failed revoke
withholds source contents. A 45-second provider read budget and a separate
final revoke attempt keep this bounded. Abrupt process loss relies on the
existing short-lived provider expiry; this is not a promise of finally-block
execution after a process kill.

Native source reads use a private fixed source-reader binding and the current
accepted Governance policy checkpoint. Provider-ID lookup preserves the actual
canonical alias. Existing positive Git admission retains its original source
path. `instance_records.enabled` is false in candidate defaults; no binding is
created or enabled by these source edits.

## Artifact And Deployment Evidence

All changes are isolated and unpublished. No live provider grant, role
commissioning, private project file read, service configuration or database
change has been performed. Native bootstrap/verification tests exercise the
actual existing issuer against its isolated loopback provider fixture; this
does not prove that a real account or runtime composition is qualified.

## Live Verification

None claimed. Source tests cover native namespace/state mismatch, proposed versus
ordinary source separation, exact selected provider, current proof recheck,
denied redirects and malformed/oversize owner responses. Real private source,
host checkout, renewal/revocation and Console proof remain separate work.

## Follow-Up

Complete the remaining source-owner selectors and full operating qualification.
The finite checkout transport now reuses the same scoped/revoked Source App read
token, derives its private managed checkout from installation identity, and
allows only clone/fetch/exact branch reference reads. It accepts no caller path,
provider URL, shell command or token. Submodules, hooks, global Git config,
ambient credentials and HTTP redirects are excluded. Interrupted or uncertain
checkout is preserved for the original OOS request, not erased. The source
candidate retains one private installation ID and distinct source-reader secret
through the existing complete-runtime lifecycle; WGCF migration ancestry must
be proven before native roles/writes are enabled. Preparation is default-off.
The host's existing OOS-to-Platform connection uses its exact private CNI gateway;
only the dedicated host connection opts into RFC1918 HTTP, with caller auth and
no public or link-local destination. These are isolated source proofs, not live
operating qualification. Keep the Metadata
App, private application contents, automatic AI requests and public Studio
records outside this new read path. Publish and activate only after later batch
approval and exact-source Security acceptance.
