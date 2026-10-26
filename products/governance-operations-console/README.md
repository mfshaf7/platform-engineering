# Governance Operations Console Platform Integration

This directory defines how the Platform supplies display-safe operator
identity, session truth, and admitted runtime observations to the Governance
Operations Console server.

## Current Shape

The current implementation extends the existing `dev-integration` session
manifest. Platform maps one admitted local operator to reviewed roles and named
authority, then publishes a private non-secret projection for the Console
server. The browser must receive only that bounded projection.

The source-staged Epic 1313 extension adds model registration and workflow
routing to the same complete-runtime composition after exact Security
acceptance. It supplies the fixed Codex binary/image, purpose-limited Vault
account lease, a separate OOS management credential, network/resource bounds
and rollback. Follow [Operate the complete Console runtime](runbooks/operate-complete-runtime.md).
Source presence alone is not commissioning or model readiness.

This is a real local session source within the single-operator
`dev-integration` trust boundary. It is not federated identity, stage evidence,
production authentication, or permission for the Console to mutate an owning
system directly.

Platform also observes an explicit policy set of Kubernetes workloads and
publishes a short-lived `console-runtime-observations/v1` projection. Runtime
readiness, freshness, source references, capability posture, and recovery
ownership stay explicit. This projection does not claim endpoint semantics,
workflow success, host telemetry, deployment approval, or Security acceptance.

The runtime policy also defines the commissioned
`portfolio-product-runtime-health/v1` projection used by Portfolio. It binds
runtime evidence to canonical product identity and recovery ownership while
keeping lifecycle, publication, issue, and health axes independent. Security
`#1271` and Platform `#1273` bind its local `dev-integration` activation.

## Ownership

- Platform issues and revokes the projection.
- Platform collects and expires the runtime observation projection.
- Console source consumes it and fails closed.
- OOS authorizes workflow commands and records attribution.
- Security Architecture approves activation of the combined boundary.

Primary operator procedure:

- [Manage the Console session projection](runbooks/manage-session-projection.md)
- [Project Console runtime observations](runbooks/project-runtime-observations.md)
- [Activate cross-domain awareness](runbooks/activate-cross-domain-awareness.md)
- [Commission Repository and Catalog operation](runbooks/commission-repository-catalog.md)
- [Commission Proposal Target](runbooks/commission-proposal-target.md)
- [Commission Agent Console](runbooks/commission-agent-console.md)
- [Commission Product Publication](runbooks/commission-product-publication.md)
- [Operate the complete Console runtime](runbooks/operate-complete-runtime.md)

Machine-readable policy:

- [session-projection-policy.yaml](session-projection-policy.yaml)
- [runtime-observation-policy.yaml](runtime-observation-policy.yaml)
- [cross-domain-activation-policy.yaml](cross-domain-activation-policy.yaml)
- [repository-catalog-commissioning-policy.yaml](repository-catalog-commissioning-policy.yaml)
- [proposal-target-commissioning-policy.yaml](proposal-target-commissioning-policy.yaml)
- [agent-console-commissioning-policy.yaml](agent-console-commissioning-policy.yaml)
- [product-publication-commissioning-policy.yaml](product-publication-commissioning-policy.yaml)
- [complete-runtime-policy.yaml](complete-runtime-policy.yaml)

The cross-domain activation path pins the approved OOS, WGCF, Console,
Workspace Governance, and Security revisions. It exposes owner APIs to the
Console server through loopback-only tunnels, keeps credentials in private
server configuration, and proves live owner-backed activity plus restart and
bounded rollback behavior. It remains local `dev-integration`, not stage or
production release authority.

Repository/Catalog commissioning extends this managed boundary with the exact
session projection and capability-specific positive, negative, restart,
rollback, and cleanup evidence required by the Security gate. It does not use
generic activity health as a substitute for workflow proof.

Proposal Target commissioning reuses the managed loopback boundary while
pinning the activated OOS source and exact Prototype Studio authority. Its
provider credential is delivered only to OOS through the dedicated Platform
identity; Console and the browser never receive it. Positive completion still
requires human-reviewed merge, target-owner readback, and canonical Proposal
acknowledgement.

Product Publication commissioning composes the activated OOS and WGCF source
gates with the existing private Console session. It pins the exact Workspace
Governance authority, Security decision, reviewed source lineage, four fresh
owner-manifest boundaries, two Workspace Registry lifecycle results, and the
complete publication receipt chain. `client` and `public` remain denied.
Platform accepts only the ordered active/internal, active/unlisted,
retired/unlisted, retired/archived, active/archived, active/unlisted, and final
active/internal states. It proves process loss, restart, rollback, restoration,
immutable history, and final cross-owner readback while retaining all
credentials outside source and browser data.

The complete-runtime coordinator adds the authenticated Platform owner route
already consumed through OOS and manages the full local composition as one
bounded lifecycle. Security binds the exact candidate Platform tree and exact
owner revisions outside the candidate source, avoiding a post-review pin
cycle. Generated credentials, resolved policies, service state, and receipts
remain operator-private; only secret-free evidence may leave that custody.
It also composes the already-approved repository-provisioning identity, WGCF
custody readiness, OOS custody state, and Console policy references. Complete
runtime status fails unless repository provisioning is executable through the
Console and the short-lived provider credential is current.

The complete-runtime extension separates reviewed execution source from fresh
canonical business records. Its existing renewal timer maintains two fixed
private owner snapshots; OOS, WGCF and the Studio Preview adapter require
freshness. The same timer projects bounded source-only owners as committed Git
snapshots beneath a fixed read-only WGCF source parent after native bootstrap;
ignored local files and host credentials are not projected. Source visibility
reserves three empty directories for the existing reviewed WG, Studio and
Console child mounts; OCI must not create targets beneath a read-only parent.
Non-empty, symlinked or otherwise unsafe reserved targets are preserved and
deny refresh, not silently erased or treated as repository evidence. The
native image regression check exercises the complete nested read-only mount
topology at the runtime UID, not just the parent snapshot.
Source visibility
does not admit the owner or accept its app. Consumers still require
short-lived checkpoints. Normal startup reuses the retained composition unit,
and status checks live Prototype and Delivery registers plus the selected
source-realization profile. See the complete-runtime runbook for the exact
Security gate, record-only boundaries, commissioning and rollback. Source
implementation is not a claim that the final Console-created app journey has
passed.

The complete-runtime path also preserves the already commissioned Product
Publication owner bindings and projects their existing server-only metadata.
Its status requires the actual Console Publication route to be live. Product
publication remains an explicit Console/OOS action with native owner evidence;
see [the complete-runtime procedure](runbooks/operate-complete-runtime.md#existing-product-publication-binding).

The normal managed frontend uses a private exact-source standalone artifact;
editing keeps hot reload in a separate source worktree. The [complete-runtime
procedure](runbooks/operate-complete-runtime.md#everyday-frontend-development-and-memory)
defines build custody, memory containment and operating proof.
